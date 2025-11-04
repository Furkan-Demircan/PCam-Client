import socket
import struct
import threading
import time
import sys
import cv2
import numpy as np
import subprocess
import shutil

try:
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
except Exception:
    print("This script requires tkinter and Pillow. Install Pillow with: pip install pillow")
    raise

# Optional virtual camera support
try:
    import pyvirtualcam
    from pyvirtualcam import PixelFormat
    VIRTUALCAM_AVAILABLE = True
except Exception:
    VIRTUALCAM_AVAILABLE = False


class FrameReceiver(threading.Thread):
    """Background thread that connects to a TCP server and receives JPEG-framed images.

    Protocol: 4-byte big-endian unsigned int length followed by JPEG frame bytes.
    """

    def __init__(self, host, port, frame_callback, status_callback, stop_event, reconnect_event, debug_callback=None):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.frame_callback = frame_callback
        self.status_callback = status_callback
        # optional callback for detailed debug logs (callable(msg))
        self.debug_callback = debug_callback
        # timestamp of last received frame (for FPS calculation)
        self._last_frame_ts = None
        self.stop_event = stop_event
        self.reconnect_event = reconnect_event
        self.sock = None

    def run(self):
        while not self.stop_event.is_set():
            # Wait for either reconnect_event or immediate attempt
            self.status_callback("Connecting...")
            if self.debug_callback:
                try:
                    self.debug_callback(f"Attempting connect to {self.host}:{self.port}")
                except Exception:
                    pass
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0)
                self.sock.connect((self.host, int(self.port)))
                try:
                    # Disable Nagle's algorithm to reduce small-packet latency
                    self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    if self.debug_callback:
                        try:
                            self.debug_callback("TCP_NODELAY set on socket (Nagle disabled)")
                        except Exception:
                            pass
                        # increase receive buffer on client side to help ffmpeg feed
                        try:
                            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
                        except Exception:
                            pass
                except Exception:
                    # Not critical; continue without failing
                    pass
                # Connected
                self.sock.settimeout(1.0)
                self.status_callback("Connected")
                if self.debug_callback:
                    try:
                        self.debug_callback("Socket connected")
                    except Exception:
                        pass

                while not self.stop_event.is_set():
                    # Read 4-byte lead. It can be:
                    # - b'H264' = start-of-h264-stream handshake (followed by width, height, fps)
                    # - or a 4-byte unsigned int length (JPEG framing), or a rotation value
                    try:
                        # Read the 4-byte header. _recvall returns:
                        #  - bytes (len==requested) on success
                        #  - None when a recv() timed out / no data yet (we should retry)
                        #  - raises ConnectionResetError when the peer closed the socket
                        size_data = self._recvall(4)
                        if size_data is None:
                            # No data yet (recv timed out) - be tolerant and loop again
                            if self.debug_callback:
                                try:
                                    self.debug_callback("No header yet (recv timed out); waiting")
                                except Exception:
                                    pass
                            continue

                        # H.264 stream handshake? (ASCII 'H264')
                        if size_data == b'H264':
                            # read width,height,fps (3x 4-byte BE ints)
                            hdr = self._recvall(12)
                            if hdr is None:
                                # timed out waiting for the rest of the header; try again
                                if self.debug_callback:
                                    try:
                                        self.debug_callback("Timed out waiting for H264 header; retrying")
                                    except Exception:
                                        pass
                                continue
                            if len(hdr) < 12:
                                raise ConnectionResetError("Incomplete H264 header")
                            width, height, fps = struct.unpack('>III', hdr)
                            if self.debug_callback:
                                try:
                                    self.debug_callback(f"H264 stream incoming: {width}x{height} @{fps}fps")
                                except Exception:
                                    pass
                            # spawn ffmpeg to decode H.264 from stdin and emit raw RGB frames on stdout
                            if shutil.which('ffmpeg') is None:
                                self.status_callback('ffmpeg not found (required for H.264 decode)')
                                raise ConnectionResetError('ffmpeg missing')

                            ff_cmd = [
                                'ffmpeg', '-hide_banner', '-loglevel', 'info',
                                '-fflags', 'nobuffer+flush_packets+discardcorrupt',
                                '-flags', 'low_delay',
                                '-avioflags', 'direct',
                                '-fflags', '+genpts',
                                '-use_wallclock_as_timestamps', '1',
                                '-f', 'h264',
                                '-i', 'pipe:0',
                                '-vsync', '0',
                                '-copyts',
                                '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'
                            ]
                            try:
                                ff = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=131072)
                            except Exception as e:
                                self.status_callback(f'ffmpeg start failed: {e}')
                                raise ConnectionResetError('ffmpeg failed')

                            # reader thread: read raw frames from ffmpeg stdout and callback
                            def ff_reader():
                                frame_size = width * height * 3
                                frame_count = 0
                                last_log_time = time.time()
                                last_fps_time = time.time()
                                fps_frame_count = 0
                                try:
                                    while not self.stop_event.is_set():
                                        try:
                                            # Log every 1 second or for first 5 frames
                                            now = time.time()
                                            should_log = frame_count < 5 or (now - last_log_time) >= 1.0
                                            
                                            if should_log and self.debug_callback:
                                                try:
                                                    self.debug_callback(f'ff_reader: Attempting read for frame #{frame_count + 1}')
                                                except Exception:
                                                    pass
                                            
                                            data = ff.stdout.read(frame_size)
                                            
                                            if not data or len(data) < frame_size:
                                                if self.debug_callback:
                                                    try:
                                                        self.debug_callback(f'ff_reader: stdout closed or incomplete frame after {frame_count} frames (got {len(data) if data else 0} bytes)')
                                                    except Exception:
                                                        pass
                                                break
                                            
                                            frame_count += 1
                                            fps_frame_count += 1
                                            
                                            # Calculate and log FPS every 2 seconds
                                            if now - last_fps_time >= 2.0:
                                                elapsed = now - last_fps_time
                                                fps = fps_frame_count / elapsed
                                                if self.debug_callback:
                                                    try:
                                                        self.debug_callback(f'Decode FPS: {fps:.1f} (total frames: {frame_count})')
                                                    except Exception:
                                                        pass
                                                fps_frame_count = 0
                                                last_fps_time = now
                                            
                                            if should_log and self.debug_callback:
                                                try:
                                                    self.debug_callback(f'ff_reader: Got complete frame #{frame_count}')
                                                    last_log_time = now
                                                except Exception:
                                                    pass
                                            
                                            arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
                                            # ffmpeg yields RGB24
                                            try:
                                                self.frame_callback(arr)
                                            except Exception as e:
                                                if self.debug_callback:
                                                    try:
                                                        self.debug_callback(f'Frame callback error: {e}')
                                                    except Exception:
                                                        pass
                                        except Exception as e:
                                            if self.debug_callback:
                                                try:
                                                    self.debug_callback(f'Frame read error: {e}')
                                                except Exception:
                                                    pass
                                            break
                                except Exception as e:
                                    if self.debug_callback:
                                        try:
                                            self.debug_callback(f'ff_reader exception: {e}')
                                        except Exception:
                                            pass
                                finally:
                                    try:
                                        ff.stdout.close()
                                    except Exception:
                                        pass

                            def stderr_reader():
                                """Background thread consuming stderr to prevent ffmpeg from blocking"""
                                line_count = 0
                                try:
                                    while not self.stop_event.is_set():
                                        try:
                                            line = ff.stderr.readline()
                                            if not line:
                                                break
                                            line_count += 1
                                            # Log only errors and warnings to avoid spam
                                            decoded = line.decode('utf-8', errors='ignore').strip()
                                            if 'error' in decoded.lower() or 'warning' in decoded.lower():
                                                if self.debug_callback:
                                                    try:
                                                        self.debug_callback(f'[ffmpeg] {decoded}')
                                                    except Exception:
                                                        pass
                                        except Exception:
                                            break
                                except Exception as e:
                                    if self.debug_callback:
                                        try:
                                            self.debug_callback(f'stderr_reader exception: {e}')
                                        except Exception:
                                            pass
                                finally:
                                    if self.debug_callback:
                                        try:
                                            self.debug_callback(f'stderr_reader: Ending after {line_count} lines')
                                        except Exception:
                                            pass
                                    try:
                                        ff.stderr.close()
                                    except Exception:
                                        pass

                            if self.debug_callback:
                                try:
                                    self.debug_callback(f'Starting H.264 decode threads')
                                except Exception:
                                    pass

                            rt = threading.Thread(target=ff_reader, daemon=True)
                            rt.start()
                            
                            st = threading.Thread(target=stderr_reader, daemon=True)
                            st.start()

                            # Now pump raw H.264 bytes from socket into ffmpeg.stdin
                            # Skip frames until we get the first keyframe (IDR with SPS/PPS)
                            waiting_for_keyframe = True
                            pending_data = b''  # Accumulate data until we find keyframe
                            bytes_sent_to_ffmpeg = 0
                            # DEBUG: Save first 10KB to file for analysis
                            debug_file = None
                            debug_bytes_saved = 0
                            try:
                                debug_file = open('d:/PCam/h264_stream_debug.h264', 'wb')
                            except Exception:
                                pass
                            
                            try:
                                while not self.stop_event.is_set():
                                    try:
                                        chunk = self.sock.recv(131072)
                                    except socket.timeout:
                                        continue
                                    if not chunk:
                                        if self.debug_callback:
                                            try:
                                                self.debug_callback(f'Socket recv returned empty after {bytes_sent_to_ffmpeg} bytes sent to ffmpeg, closing')
                                            except Exception:
                                                pass
                                        break
                                    
                                    # Wait for first keyframe (starts with 0x00 0x00 0x00 0x01 0x67 = SPS or 0x65 = IDR)
                                    if waiting_for_keyframe:
                                        # Accumulate data
                                        pending_data += chunk
                                        # Look for SPS (0x67) or IDR (0x65) NAL unit
                                        found_keyframe = False
                                        for i in range(len(pending_data) - 4):
                                            if pending_data[i:i+4] == b'\x00\x00\x00\x01':
                                                nal_type = pending_data[i+4] & 0x1F
                                                if nal_type == 7 or nal_type == 5:  # SPS or IDR
                                                    found_keyframe = True
                                                    if self.debug_callback:
                                                        try:
                                                            nal_name = 'SPS' if nal_type == 7 else 'IDR'
                                                            self.debug_callback(f'Found first keyframe: {nal_name} at offset {i}, buffered {len(pending_data)} bytes total')
                                                        except Exception:
                                                            pass
                                                    # Start from this position
                                                    chunk = pending_data[i:]
                                                    pending_data = b''
                                                    waiting_for_keyframe = False
                                                    break
                                        if waiting_for_keyframe:
                                            # Still waiting, continue accumulating
                                            # Keep last 10MB max to avoid memory issues
                                            if len(pending_data) > 10 * 1024 * 1024:
                                                pending_data = pending_data[-1024*1024:]
                                            continue
                                    
                                    # DEBUG: Save first chunks
                                    if debug_file and debug_bytes_saved < 100000:
                                        debug_file.write(chunk)
                                        debug_bytes_saved += len(chunk)
                                        if debug_bytes_saved >= 100000:
                                            debug_file.close()
                                            debug_file = None
                                            if self.debug_callback:
                                                try:
                                                    self.debug_callback(f'Saved first {debug_bytes_saved} bytes to h264_stream_debug.h264')
                                                except Exception:
                                                    pass
                                    try:
                                        ff.stdin.write(chunk)
                                        ff.stdin.flush()
                                        bytes_sent_to_ffmpeg += len(chunk)
                                        # Log progress every 1MB
                                        if bytes_sent_to_ffmpeg % 1000000 < len(chunk):
                                            if self.debug_callback:
                                                try:
                                                    mb = bytes_sent_to_ffmpeg / 1000000
                                                    self.debug_callback(f'Sent {mb:.1f}MB to ffmpeg')
                                                except Exception:
                                                    pass
                                    except BrokenPipeError as e:
                                        if self.debug_callback:
                                            try:
                                                self.debug_callback(f'ffmpeg stdin broken pipe after {bytes_sent_to_ffmpeg} bytes: {e}')
                                            except Exception:
                                                pass
                                        break
                                    except Exception as e:
                                        if self.debug_callback:
                                            try:
                                                self.debug_callback(f'ffmpeg stdin write error after {bytes_sent_to_ffmpeg} bytes: {e}')
                                            except Exception:
                                                pass
                                        break
                            finally:
                                if debug_file:
                                    try:
                                        debug_file.close()
                                    except Exception:
                                        pass
                                try:
                                    ff.stdin.close()
                                except Exception:
                                    pass
                                # Wait for reader thread to finish
                                rt.join(timeout=1.0)
                                # Terminate ffmpeg if still running
                                try:
                                    ff.terminate()
                                    ff.wait(timeout=1.0)
                                except Exception:
                                    try:
                                        ff.kill()
                                    except Exception:
                                        pass
                                break

                        # Not H.264: treat as the previous JPEG-style framing (with optional rotation header)
                        first_val = struct.unpack('>I', size_data)[0]
                        rotation = None
                        if first_val in (0, 90, 180, 270, 360):
                            rotation = first_val
                            # next 4 bytes are the frame size
                            size_data2 = self._recvall(4)
                            if size_data2 is None:
                                # timed out waiting for the frame size; retry outer loop
                                if self.debug_callback:
                                    try:
                                        self.debug_callback("Timed out waiting for frame size; retrying")
                                    except Exception:
                                        pass
                                continue
                            if len(size_data2) < 4:
                                raise ConnectionResetError("Incomplete frame size")
                            frame_size = struct.unpack('>I', size_data2)[0]
                        else:
                            frame_size = first_val

                        if self.debug_callback:
                            try:
                                self.debug_callback(f"Incoming frame size: {frame_size} bytes (rotation={rotation})")
                            except Exception:
                                pass

                        frame_data = self._recvall(frame_size)
                        if frame_data is None:
                            # timed out while waiting for full frame bytes; continue and allow more time
                            if self.debug_callback:
                                try:
                                    self.debug_callback(f"Timed out waiting for full frame ({frame_size} bytes); retrying")
                                except Exception:
                                    pass
                            continue
                        if len(frame_data) < frame_size:
                            raise ConnectionResetError("Incomplete frame")

                        # timing: record receive timestamp and compute interval/fps
                        try:
                            t_recv = time.time()
                            if self.debug_callback:
                                try:
                                    self.debug_callback(f"Frame recv: {frame_size} bytes @ {t_recv:.3f}")
                                    if getattr(self, '_last_frame_ts', None) is not None:
                                        dt = t_recv - self._last_frame_ts
                                        if dt > 0:
                                            fps = 1.0 / dt
                                            self.debug_callback(f"Inter-frame dt={dt:.3f}s fps={fps:.1f}")
                                except Exception:
                                    pass
                            self._last_frame_ts = t_recv
                        except Exception:
                            pass

                        # decode JPEG frame
                        arr = np.frombuffer(frame_data, np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            # If the sender included a rotation header, apply it here
                            try:
                                if rotation == 90:
                                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                                elif rotation == 180:
                                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                                elif rotation == 270:
                                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
                                # convert BGR->RGB for PIL
                                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            except Exception:
                                # fallback: just convert color
                                try:
                                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                                except Exception:
                                    pass
                            self.frame_callback(frame)
                    except socket.timeout:
                        # allow loop to check stop_event or reconnect_event
                        pass
                    except Exception as e:
                        # Connection lost or decoding error
                        self.status_callback(f"Connection lost: {e}")
                        if self.debug_callback:
                            try:
                                self.debug_callback(f"Exception during frame read/decode: {e}")
                            except Exception:
                                pass
                        break

                    # if a manual reconnect requested
                    if self.reconnect_event.is_set():
                        self.reconnect_event.clear()
                        self.status_callback("Reconnecting...")
                        break

                # close socket and try again if not stopped
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

                if self.stop_event.is_set():
                    break

                # If reconnect wasn't requested, wait until reconnect_event or stop
                if not self.reconnect_event.is_set():
                    # show device not found then wait
                    self.status_callback("Device not Found")
                    # Sleep in short increments to be responsive
                    wait_seconds = 0
                    while not (self.reconnect_event.is_set() or self.stop_event.is_set()) and wait_seconds < 5:
                        time.sleep(0.1)
                        wait_seconds += 0.1

            except (ConnectionRefusedError, socket.timeout) as e:
                self.status_callback(f"Connection failed: {e}")
                # Show device not found and wait for reconnect or stop
                self.status_callback("Device not Found")
                wait_seconds = 0
                while not (self.reconnect_event.is_set() or self.stop_event.is_set()) and wait_seconds < 3:
                    time.sleep(0.1)
                    wait_seconds += 0.1
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
                continue
            except Exception as e:
                self.status_callback(f"Unexpected error: {e}")
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass
                self.sock = None
                time.sleep(1)
                continue

    def _recvall(self, size):
        data = b''
        while len(data) < size and not self.stop_event.is_set():
            try:
                to_read = size - len(data)
                chunk = self.sock.recv(to_read)
                if not chunk:
                    # socket closed by peer - raise so caller tears down the connection
                    if self.debug_callback:
                        try:
                            self.debug_callback(f"recv returned 0 bytes while expecting {size} (got {len(data)}) - peer closed")
                        except Exception:
                            pass
                    raise ConnectionResetError("Socket closed by peer")
                data += chunk
            except socket.timeout:
                # return partial to outer logic which will handle it
                continue
        # if we exited the loop without collecting the full size, return None
        if len(data) < size:
            if self.debug_callback:
                try:
                    self.debug_callback(f"recvall timed out/stop: expected {size}, got {len(data)}")
                except Exception:
                    pass
            return None
        return data


class PCamClientGUI:
    # Base long side for preview (pixels). Horizontal preview will be 16:9 (w x h),
    # vertical preview will be 9:16 (w x h) using this long side.
    PREVIEW_LONG = 640

    def __init__(self, root):
        self.root = root
        root.title('PCam Client')

        # top-level control vars
        self.host_var = tk.StringVar(value='127.0.0.1')
        self.port_var = tk.StringVar(value='8080')
        self.status_var = tk.StringVar(value='Idle')

        self.latest_frame = None
        self.photoimage = None
        # rotation setting (degrees). Default 360 = no rotation
        self.rotate_var = tk.IntVar(value=360)

        # threading controls
        self.stop_event = threading.Event()
        self.reconnect_event = threading.Event()
        self.receiver = None

        # virtual cam controls
        self.vcam_enabled_var = tk.BooleanVar(value=False)
        self.vcam_cam = None
        self.vcam_thread = None
        self.vcam_stop_event = threading.Event()
        self.vcam_fps = 60
        # optional UI-controlled fps for virtual camera
        self.vcam_fps_var = tk.IntVar(value=self.vcam_fps)
        # flag to avoid spamming source size logs
        self._source_logged = False
        # virtual camera resolution (defaults to preview 640x360)
        self.vcam_width_var = tk.IntVar(value=640)
        self.vcam_height_var = tk.IntVar(value=360)

        # (Direct OBS virtual camera setup removed — using background vcam worker instead)

        self._build_ui()

        # key bindings
        root.bind('<r>', lambda e: self.on_reset())
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        # start receiver thread immediately
        self.start_receiver()
        # attempt to start adb port forwarding if adb is available
        try:
            self._start_adb_forward()
        except Exception:
            pass
        # start GUI update loop
        self._update_preview()

    def _build_ui(self):
        # main container with two columns
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        # left frame - split into top (server settings) and bottom (camera settings)
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        # top: server settings
        left_top = ttk.Frame(left)
        left_top.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(left_top, text='Server Settings', font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

        frm = ttk.Frame(left_top)
        frm.pack(anchor=tk.W, pady=4)
        ttk.Label(frm, text='Host:').grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(frm, textvariable=self.host_var, width=20).grid(row=0, column=1, sticky=tk.W)

        frm2 = ttk.Frame(left_top)
        frm2.pack(anchor=tk.W, pady=4)
        ttk.Label(frm2, text='Port:').grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(frm2, textvariable=self.port_var, width=8).grid(row=0, column=1, sticky=tk.W)

        btn_frame = ttk.Frame(left_top)
        btn_frame.pack(anchor=tk.W, pady=8)
        self.connect_btn = ttk.Button(btn_frame, text='Connect', command=self.on_connect)
        self.connect_btn.pack(side=tk.LEFT)
        self.reset_btn = ttk.Button(btn_frame, text='Reset (r)', command=self.on_reset)
        self.reset_btn.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(left_top, text='Status:').pack(anchor=tk.W, pady=(12, 0))
        ttk.Label(left_top, textvariable=self.status_var, foreground='blue').pack(anchor=tk.W)

        # bottom: camera settings (rotation etc.)
        left_bottom = ttk.LabelFrame(left, text='Camera Settings')
        left_bottom.pack(fill=tk.X, expand=False)

        ttk.Label(left_bottom, text='Rotate:').grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        rot_frame = ttk.Frame(left_bottom)
        rot_frame.grid(row=0, column=1, sticky=tk.W, padx=6, pady=6)

        # rotation choices: 90,180,270,360 (360 == no rotation)
        for val, lbl in ((90, '90'), (180, '180'), (270, '270'), (360, '360')):
            ttk.Radiobutton(rot_frame, text=lbl, variable=self.rotate_var, value=val).pack(side=tk.LEFT, padx=2)

        # optional debug checkbox below settings
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_bottom, text='Show debug logs', variable=self.debug_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(0,6))

        # virtual cam checkbox
        vcam_row = 2
        if VIRTUALCAM_AVAILABLE:
            ttk.Checkbutton(left_bottom, text='Send to virtual camera', variable=self.vcam_enabled_var, command=self._on_vcam_toggle).grid(row=vcam_row, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(2,6))
            # small controls to choose virtual camera resolution
            res_frame = ttk.Frame(left_bottom)
            res_frame.grid(row=vcam_row+1, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(0,6))
            ttk.Label(res_frame, text='VCam Res:').pack(side=tk.LEFT)
            ttk.Entry(res_frame, textvariable=self.vcam_width_var, width=6).pack(side=tk.LEFT, padx=(6,2))
            ttk.Label(res_frame, text='x').pack(side=tk.LEFT)
            ttk.Entry(res_frame, textvariable=self.vcam_height_var, width=6).pack(side=tk.LEFT, padx=(2,6))
            ttk.Label(res_frame, text='FPS:').pack(side=tk.LEFT, padx=(6,2))
            ttk.Entry(res_frame, textvariable=self.vcam_fps_var, width=4).pack(side=tk.LEFT, padx=(2,6))
            ttk.Label(res_frame, text='(change while stopped)').pack(side=tk.LEFT, padx=(4,0))
        else:
            ttk.Label(left_bottom, text='pyvirtualcam not installed', foreground='gray').grid(row=vcam_row, column=0, columnspan=2, sticky=tk.W, padx=6, pady=(2,6))

        # right frame - preview and controls
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # preview canvas
        self.preview_label = ttk.Label(right)
        self.preview_label.pack()
        self._set_preview_placeholder('Device not Found')

        # reset button under preview (fixed size preview area)
        lower = ttk.Frame(right)
        lower.pack(pady=(8, 0))
        ttk.Button(lower, text='Reset (r)', command=self.on_reset).pack()

    def _set_preview_placeholder(self, text):
        # create an image with text centered
        w, h = self._get_preview_size()
        img = np.zeros((h, w, 3), dtype=np.uint8)
        # dark background
        img[:] = (30, 30, 30)
        # put text
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.0
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (w - tw) // 2
        y = (h + th) // 2
        cv2.putText(img, text, (x, y), font, scale, (200, 200, 200), thickness, cv2.LINE_AA)
        # convert to PIL image
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(img_rgb)
        pil = pil.resize((w, h))
        self.photoimage = ImageTk.PhotoImage(pil)
        self.preview_label.configure(image=self.photoimage)

    def start_receiver(self):
        # stop old thread if any
        self.stop_receiver()
        self.stop_event.clear()
        self.reconnect_event.clear()
        self.receiver = FrameReceiver(
            host=self.host_var.get(),
            port=self.port_var.get(),
            frame_callback=self._on_frame,
            status_callback=self._on_status,
            stop_event=self.stop_event,
            reconnect_event=self.reconnect_event,
            debug_callback=self._debug_log,
        )
        self.receiver.start()

    def _get_preview_size(self):
        """Return (w, h) for the preview area based on current rotation selection.

        If rotation is 90 or 270 we display vertically in 16:9 (width < height).
        If rotation is 180 or 360 we display horizontally in 16:9 (width > height).
        """
        try:
            rot = int(self.rotate_var.get())
        except Exception:
            rot = 360

        if rot in (90, 270):
            # vertical: long side is height
            h = self.PREVIEW_LONG
            w = int(h * 9 / 16)
        else:
            # horizontal: long side is width
            w = self.PREVIEW_LONG
            h = int(w * 9 / 16)
        return w, h

    def _on_vcam_toggle(self):
        """Called when the user toggles the Send to virtual camera checkbox."""
        enabled = bool(self.vcam_enabled_var.get())
        if enabled:
            self._start_vcam_thread()
        else:
            self._stop_vcam_thread()

    def _start_vcam_thread(self):
        if not VIRTUALCAM_AVAILABLE:
            self._on_status('pyvirtualcam not available')
            self.vcam_enabled_var.set(False)
            return
        if self.vcam_thread and self.vcam_thread.is_alive():
            return
        # start worker
        self.vcam_stop_event.clear()
        self.vcam_thread = threading.Thread(target=self._vcam_worker, daemon=True)
        self.vcam_thread.start()

    def _stop_vcam_thread(self):
        if self.vcam_thread and self.vcam_thread.is_alive():
            self.vcam_stop_event.set()
            self.vcam_thread.join(timeout=1.0)
        self.vcam_thread = None
        # close camera if open
        try:
            if self.vcam_cam is not None:
                try:
                    self.vcam_cam.close()
                except Exception:
                    pass
        finally:
            self.vcam_cam = None

    def _vcam_worker(self):
        """Background worker that sends the latest frame to the virtual camera at vcam_fps."""
        # determine initial size from user-configured vcam resolution (fallback to preview size)
        try:
            w = int(self.vcam_width_var.get())
            h = int(self.vcam_height_var.get())
            if w <= 0 or h <= 0:
                raise ValueError()
        except Exception:
            w, h = self._get_preview_size()
        # read fps from UI var (fallback to default self.vcam_fps)
        try:
            fps = int(self.vcam_fps_var.get())
            if fps <= 0:
                raise ValueError()
        except Exception:
            fps = self.vcam_fps
        try:
            cam = pyvirtualcam.Camera(width=w, height=h, fps=fps, fmt=PixelFormat.BGR)
        except Exception as e:
            self._on_status(f"Failed to open virtual cam: {e}")
            self.vcam_enabled_var.set(False)
            return
        self.vcam_cam = cam
        # show actual opened size/fps (some backends may adjust)
        try:
            actual_fps = getattr(cam, 'fps', fps)
        except Exception:
            actual_fps = fps
        self._on_status(f"VCam opened {cam.width}x{cam.height} @{actual_fps}fps")

        # loop and send frames
        try:
            while not self.vcam_stop_event.is_set():
                frame = None
                if self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                else:
                    # black frame
                    frame = np.zeros((h, w, 3), dtype=np.uint8)

                # ensure correct rotation/size
                try:
                    rot = int(self.rotate_var.get())
                except Exception:
                    rot = 360
                if rot == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif rot == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif rot == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # resize to cam size if needed
                try:
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                except Exception:
                    frame_bgr = frame
                if frame_bgr.shape[1] != cam.width or frame_bgr.shape[0] != cam.height:
                    frame_bgr = cv2.resize(frame_bgr, (cam.width, cam.height))

                try:
                    cam.send(frame_bgr)
                    cam.sleep_until_next_frame()
                except Exception:
                    # if send fails, try to continue, but report status
                    self._on_status('Virtual cam send error')
                    time.sleep(0.1)
        finally:
            try:
                cam.close()
            except Exception:
                pass
            self.vcam_cam = None
            self._on_status('Virtual camera stopped')

    def stop_receiver(self):
        if self.receiver and self.receiver.is_alive():
            self.stop_event.set()
            # also set reconnect to wake it if sleeping
            self.reconnect_event.set()
            self.receiver.join(timeout=2.0)
        self.receiver = None
        self.stop_event.clear()

        # also stop vcam if running
        self._stop_vcam_thread()

    def on_connect(self):
        # update host/port and restart receiver
        self.start_receiver()

    def on_reset(self):
        # emulate pressing 'r' -> request reconnect
        self._on_status('User requested reset')
        # set host/port from entries into receiver
        if self.receiver and self.receiver.is_alive():
            # trigger reconnect
            self.reconnect_event.set()
        else:
            # start a new receiver
            self.start_receiver()

    def _on_frame(self, frame_rgb):
        # frame_rgb: numpy array RGB
        self.latest_frame = frame_rgb
        # log source size once for diagnosis
        try:
            if not getattr(self, '_source_logged', False):
                w = frame_rgb.shape[1]
                h = frame_rgb.shape[0]
                self._on_status(f"Source {w}x{h}")
                self._source_logged = True
        except Exception:
            pass

    def _on_status(self, msg):
        # called from background threads; ensure thread-safe update
        def upd():
            self.status_var.set(msg)
        try:
            self.root.after(0, upd)
        except Exception:
            pass

    def _debug_log(self, msg):
        """Print debug log lines to stderr when 'Show debug logs' is enabled in UI.

        This is safe to call from background threads.
        """
        try:
            if getattr(self, 'debug_var', None) and self.debug_var.get():
                t = time.strftime('%H:%M:%S')
                # print to stderr so it's visible even if stdout is used
                print(f"[DEBUG {t}] {msg}", file=sys.stderr, flush=True)
        except Exception as e:
            # If debug logging fails, at least show the error
            print(f"[DEBUG ERROR] {e}: {msg}", file=sys.stderr, flush=True)

    def _update_preview(self):
        frame_to_send = None

        if self.latest_frame is not None:
            try:
                frame = self.latest_frame

                # apply rotation if requested (90/180/270). 360 == no rotation
                try:
                    rot = int(self.rotate_var.get())
                except Exception:
                    rot = 360

                if rot == 90:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                elif rot == 180:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                elif rot == 270:
                    frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                frame_to_send = frame

                # update GUI preview
                pil = Image.fromarray(frame)
                w, h = self._get_preview_size()
                pil = pil.resize((w, h))
                self.photoimage = ImageTk.PhotoImage(pil)
                self.preview_label.configure(image=self.photoimage)

            except Exception as e:
                self._set_preview_placeholder('Decode Error')

        # schedule next update
        delay_ms = 30 # GUI'yi 30ms'de bir güncelle
        self.root.after(delay_ms, self._update_preview)

    def on_close(self):
        self.stop_event.set()
        self.reconnect_event.set()
        # allow receiver to exit
        if self.receiver and self.receiver.is_alive():
            self.receiver.join(timeout=1.0)
        # stop virtual camera thread if running
        self._stop_vcam_thread()
        # stop adb forward if we started it
        try:
            self._stop_adb_forward()
        except Exception:
            pass
        self.root.destroy()

    # --- ADB forward helpers -------------------------------------------------
    def _start_adb_forward(self):
        """Start 'adb forward tcp:8080 tcp:8080' if adb exists in PATH.

        Sets self._adb_forwarded = True on success.
        """
        adb_path = shutil.which('adb')
        if not adb_path:
            # adb not available; nothing to do
            return False
        # run adb forward
        try:
            # use a subprocess call; do not raise on non-zero so we can report
            res = subprocess.run([adb_path, 'forward', 'tcp:8080', 'tcp:8080'], capture_output=True, text=True)
            if res.returncode == 0:
                self._adb_forwarded = True
                self._on_status('ADB forward started')
                return True
            else:
                # log failure to status
                msg = res.stderr.strip() or res.stdout.strip()
                self._on_status(f'ADB forward failed: {msg}')
                return False
        except Exception as e:
            self._on_status(f'ADB forward error: {e}')
            return False

    def _stop_adb_forward(self):
        """Remove the adb forward we previously created.

        Uses 'adb forward --remove tcp:8080'.
        """
        if not getattr(self, '_adb_forwarded', False):
            return False
        adb_path = shutil.which('adb')
        if not adb_path:
            return False
        try:
            res = subprocess.run([adb_path, 'forward', '--remove', 'tcp:8080'], capture_output=True, text=True)
            if res.returncode == 0:
                self._adb_forwarded = False
                self._on_status('ADB forward removed')
                return True
            else:
                msg = res.stderr.strip() or res.stdout.strip()
                self._on_status(f'ADB remove failed: {msg}')
                return False
        except Exception as e:
            self._on_status(f'ADB remove error: {e}')
            return False


def main():
    root = tk.Tk()
    app = PCamClientGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()