import os
import shutil
from pathlib import Path
from datetime import datetime
from operator import itemgetter
import piexif
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading


class CameraRenamerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Camera Renamer - Safe Version")
        self.root.geometry("700x650")
        self.root.resizable(True, True)
        
        self.camera_dirs = {}
        self.output_dir = None
        self.keep_raw = tk.BooleanVar(value=True)
        self.move_files = tk.BooleanVar(value=False)
        
        self.setup_ui()
    
    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="Multi-Camera Photo Renamer", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Warning label
        warning = tk.Label(self.root, text="⚠️ SAFETY: Output folder CANNOT be the same as any input folder", 
                          font=("Arial", 10, "bold"), fg="red")
        warning.pack(pady=5)
        
        # Camera selection frame
        camera_frame = tk.LabelFrame(self.root, text="Camera Sources (Input Folders)", padx=10, pady=10)
        camera_frame.pack(fill="x", padx=10, pady=5)
        
        self.camera_labels = {}
        for i in range(1, 4):
            frame = tk.Frame(camera_frame)
            frame.pack(fill="x", pady=5)
            
            label = tk.Label(frame, text=f"Camera {i}:", width=12, anchor="w")
            label.pack(side="left", padx=5)
            
            path_label = tk.Label(frame, text="Not selected", fg="gray", anchor="w")
            path_label.pack(side="left", fill="x", expand=True, padx=5)
            self.camera_labels[i] = path_label
            
            clear_btn = tk.Button(frame, text="Clear", command=lambda x=i: self.clear_camera(x),
                                 bg="#FF6B6B", fg="white", width=6)
            clear_btn.pack(side="right", padx=2)
            
            btn = tk.Button(frame, text="Browse", command=lambda x=i: self.select_camera(x))
            btn.pack(side="right", padx=2)
        
        # Output selection frame
        output_frame = tk.LabelFrame(self.root, text="Output Folder (Must be different!)", padx=10, pady=10)
        output_frame.pack(fill="x", padx=10, pady=5)
        
        output_inner = tk.Frame(output_frame)
        output_inner.pack(fill="x", pady=5)
        
        output_lbl = tk.Label(output_inner, text="Output:", width=12, anchor="w")
        output_lbl.pack(side="left", padx=5)
        
        self.output_label = tk.Label(output_inner, text="Not selected", fg="gray", anchor="w")
        self.output_label.pack(side="left", fill="x", expand=True, padx=5)
        
        clear_output_btn = tk.Button(output_inner, text="Clear", command=self.clear_output,
                                     bg="#FF6B6B", fg="white", width=6)
        clear_output_btn.pack(side="right", padx=2)
        
        output_btn = tk.Button(output_inner, text="Browse", command=self.select_output)
        output_btn.pack(side="right", padx=2)
        
        # Options frame
        options_frame = tk.LabelFrame(self.root, text="Options", padx=10, pady=10)
        options_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Checkbutton(options_frame, text="Keep RAF/RAW files (unchecked = JPG only)", 
                      variable=self.keep_raw).pack(anchor="w")
        tk.Checkbutton(options_frame, text="Move files (unchecked = copy, keeps originals)", 
                      variable=self.move_files).pack(anchor="w")
        
        # Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Clear All", width=12, command=self.clear_all,
                 bg="#FF6B6B", fg="white", padx=10).pack(side="left", padx=5)
        tk.Button(button_frame, text="Preview", width=12, command=self.preview,
                 bg="#4CAF50", fg="white", padx=10).pack(side="left", padx=5)
        tk.Button(button_frame, text="Process", width=12, command=self.process,
                 bg="#2196F3", fg="white", padx=10).pack(side="left", padx=5)
        
        # Output text
        self.output_text = scrolledtext.ScrolledText(self.root, height=15, width=80)
        self.output_text.pack(fill="both", expand=True, padx=10, pady=5)
    
    def normalize_path(self, path):
        """Normalize path for comparison (resolve, absolute, lowercase on Windows)"""
        p = Path(path).resolve().absolute()
        if os.name == 'nt':
            return str(p).lower()
        return str(p)
    
    def validate_folders(self):
        """Validate that output folder is not the same as any input folder"""
        if not self.output_dir:
            self.log("✗ Please select an output folder")
            return False
        
        if not self.camera_dirs:
            self.log("✗ Please select at least one camera folder")
            return False
        
        output_normalized = self.normalize_path(self.output_dir)
        
        for cam_num, cam_path in self.camera_dirs.items():
            cam_normalized = self.normalize_path(cam_path)
            
            if output_normalized == cam_normalized:
                error_msg = (f"❌ CRITICAL ERROR ❌\n\n"
                           f"Output folder CANNOT be the same as Camera {cam_num} folder!\n\n"
                           f"This would cause DATA LOSS.\n\n"
                           f"Camera {cam_num}: {cam_path}\n"
                           f"Output: {self.output_dir}\n\n"
                           f"Please select a DIFFERENT output folder.")
                messagebox.showerror("Folder Conflict Detected", error_msg)
                self.log(f"✗ ERROR: Output folder is same as Camera {cam_num} folder!")
                return False
            
            if output_normalized.startswith(cam_normalized + os.sep):
                error_msg = (f"❌ WARNING ❌\n\n"
                           f"Output folder is INSIDE Camera {cam_num} folder!\n\n"
                           f"This could cause issues.\n\n"
                           f"Camera {cam_num}: {cam_path}\n"
                           f"Output: {self.output_dir}\n\n"
                           f"Please select a separate output folder.")
                messagebox.showwarning("Nested Folder Warning", error_msg)
                self.log(f"⚠ WARNING: Output folder is inside Camera {cam_num} folder!")
                return False
            
            if cam_normalized.startswith(output_normalized + os.sep):
                error_msg = (f"❌ WARNING ❌\n\n"
                           f"Camera {cam_num} folder is INSIDE Output folder!\n\n"
                           f"This could cause issues.\n\n"
                           f"Camera {cam_num}: {cam_path}\n"
                           f"Output: {self.output_dir}\n\n"
                           f"Please select a separate output folder.")
                messagebox.showwarning("Nested Folder Warning", error_msg)
                self.log(f"⚠ WARNING: Camera {cam_num} folder is inside Output folder!")
                return False
        
        return True
    
    def select_camera(self, camera_num):
        folder = filedialog.askdirectory(title=f"Select Camera {camera_num} folder")
        if folder:
            self.camera_dirs[camera_num] = folder
            display_name = folder if len(folder) <= 40 else "..." + folder[-37:]
            self.camera_labels[camera_num].config(text=display_name, fg="black")
            self.log(f"✓ Camera {camera_num} set to: {folder}")
    
    def select_output(self):
        folder = filedialog.askdirectory(title="Select Output folder (must be different from inputs!)")
        if folder:
            self.output_dir = folder
            display_name = folder if len(folder) <= 40 else "..." + folder[-37:]
            self.output_label.config(text=display_name, fg="black")
            self.log(f"✓ Output set to: {folder}")
    
    def clear_camera(self, camera_num):
        """Clear a specific camera folder selection"""
        if camera_num in self.camera_dirs:
            del self.camera_dirs[camera_num]
            self.camera_labels[camera_num].config(text="Not selected", fg="gray")
            self.log(f"✗ Camera {camera_num} cleared")
    
    def clear_output(self):
        """Clear output folder selection"""
        self.output_dir = None
        self.output_label.config(text="Not selected", fg="gray")
        self.log("✗ Output folder cleared")
    
    def clear_all(self):
        """Clear all folder selections"""
        for i in range(1, 4):
            if i in self.camera_dirs:
                del self.camera_dirs[i]
                self.camera_labels[i].config(text="Not selected", fg="gray")
        
        self.output_dir = None
        self.output_label.config(text="Not selected", fg="gray")
        
        self.output_text.delete(1.0, "end")
        self.log("✗ All folders cleared")
    
    def log(self, message):
        self.output_text.insert("end", message + "\n")
        self.output_text.see("end")
        self.root.update()
    
    def preview(self):
        self.output_text.delete(1.0, "end")
        self.log("=== PREVIEW MODE ===\n")
        
        if not self.validate_folders():
            return
        
        self._process_internal(copy_files=False)
    
    def process(self):
        self.output_text.delete(1.0, "end")
        
        if not self.validate_folders():
            return
        
        if self.move_files.get():
            confirm_msg = ("⚠️ MOVE MODE ENABLED ⚠️\n\n"
                          "Original files will be MOVED (not copied).\n"
                          "This will remove files from the camera folders.\n\n"
                          "Are you sure you want to continue?")
            if not messagebox.askyesno("Confirm Move Operation", confirm_msg):
                self.log("✗ Operation cancelled by user")
                return
        
        if messagebox.askyesno("Confirm", "Start processing files?"):
            thread = threading.Thread(target=self._process_internal, args=(True,))
            thread.daemon = True
            thread.start()
    
    def _process_internal(self, copy_files=True):
        try:
            output_dir = Path(self.output_dir)
            renamer = CombinedCameraRenamer(output_dir, self.keep_raw.get(), self.move_files.get())
            
            for cam_num, cam_path in sorted(self.camera_dirs.items()):
                renamer.add_camera_source(cam_num, cam_path)
            
            self.log("\n📹 Collecting files...\n")
            if not renamer.collect_and_sort_files(self):
                return
            
            self.log("\n📋 Processing files...\n")
            renamer.rename_and_copy(copy_files, self)
            
            if copy_files:
                renamer.create_detailed_report()
                self.log(f"\n✓ Complete! Files saved to: {output_dir}")
            else:
                self.log("\n✓ Preview complete!")
                
        except Exception as e:
            self.log(f"\n✗ Error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")


class CombinedCameraRenamer:
    def __init__(self, output_dir=None, keep_raw=True, move_files=False):
        self.camera_sources = {}
        self.all_files = []
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "combined_footage"
        self.keep_raw = keep_raw
        self.move_files = move_files
    
    def add_camera_source(self, camera_num, source_path):
        self.camera_sources[camera_num] = Path(source_path)
    
    def get_timestamp(self, file_path):
        try:
            exif_dict = piexif.load(str(file_path))
            if piexif.ExifIFD.DateTimeOriginal in exif_dict["Exif"]:
                date_str = exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal].decode()
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except:
            pass
        return datetime.fromtimestamp(file_path.stat().st_mtime)
    
    def collect_and_sort_files(self, gui):
        """Collect files and handle RAF+JPG pairs properly to avoid duplicates"""
        file_dict = {}
        
        for camera_num, source_path in sorted(self.camera_sources.items()):
            if not source_path.exists():
                gui.log(f"✗ Camera {camera_num} path does not exist: {source_path}")
                return False
            
            file_extensions = ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']
            if self.keep_raw:
                file_extensions.extend(['*.raf', '*.RAF', '*.arw', '*.ARW'])
            
            files_found = []
            for ext in file_extensions:
                files_found.extend(source_path.glob(ext))
            
            gui.log(f"✓ Camera {camera_num}: Found {len(files_found)} files")
            
            # Group files by base name to detect pairs
            for file_path in files_found:
                base_name = file_path.stem.upper()
                timestamp = self.get_timestamp(file_path)
                
                if base_name not in file_dict:
                    file_dict[base_name] = {
                        'camera': camera_num,
                        'timestamp': timestamp,
                        'jpg': None,
                        'raw': None
                    }
                
                ext_lower = file_path.suffix.lower()
                if ext_lower in ['.jpg', '.jpeg']:
                    file_dict[base_name]['jpg'] = file_path
                elif ext_lower in ['.raf', '.arw']:
                    file_dict[base_name]['raw'] = file_path
                    file_dict[base_name]['timestamp'] = timestamp
        
        # Convert dict to list
        for base_name, file_info in file_dict.items():
            entry = {
                'camera': file_info['camera'],
                'timestamp': file_info['timestamp'],
                'jpg_path': file_info['jpg'],
                'raw_path': file_info['raw'],
                'base_name': base_name
            }
            self.all_files.append(entry)
        
        if not self.all_files:
            gui.log("✗ No files found")
            return False
        
        self.all_files.sort(key=itemgetter('timestamp'))
        
        total_count = sum(1 for f in self.all_files if f['jpg_path']) + \
                     sum(1 for f in self.all_files if f['raw_path'])
        
        gui.log(f"\n✓ Total file entries: {len(self.all_files)}")
        gui.log(f"✓ Total individual files: {total_count}")
        return True
    
    def rename_and_copy(self, copy_files, gui):
        if not copy_files:
            gui.log("Preview mode - no files will be copied/moved\n")
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            action = "Moving" if self.move_files else "Copying"
            gui.log(f"{action} files to: {self.output_dir}\n")
        
        sequence_num = 0
        
        for file_entry in self.all_files:
            sequence_num += 1
            padded_seq = str(sequence_num).zfill(4) if sequence_num < 10000 else str(sequence_num)
            
            timestamp_str = file_entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            cam_num = file_entry['camera']
            
            # Process JPG if exists
            if file_entry['jpg_path']:
                jpg_path = file_entry['jpg_path']
                new_jpg_name = f"DSCF{padded_seq}.JPG"
                new_jpg_path = self.output_dir / new_jpg_name
                
                gui.log(f"[{sequence_num:5d}] CAM{cam_num} | {timestamp_str} | {jpg_path.name}")
                gui.log(f"           → {new_jpg_name}")
                
                if copy_files:
                    if self.move_files:
                        shutil.move(str(jpg_path), str(new_jpg_path))
                    else:
                        shutil.copy2(str(jpg_path), str(new_jpg_path))
            
            # Process RAW if exists
            if file_entry['raw_path']:
                raw_path = file_entry['raw_path']
                raw_ext = raw_path.suffix.upper()
                new_raw_name = f"DSCF{padded_seq}{raw_ext}"
                new_raw_path = self.output_dir / new_raw_name
                
                if not file_entry['jpg_path']:
                    gui.log(f"[{sequence_num:5d}] CAM{cam_num} | {timestamp_str} | {raw_path.name}")
                else:
                    gui.log(f"           + {raw_path.name}")
                gui.log(f"           → {new_raw_name}")
                
                if copy_files:
                    if self.move_files:
                        shutil.move(str(raw_path), str(new_raw_path))
                    else:
                        shutil.copy2(str(raw_path), str(new_raw_path))
    
    def create_detailed_report(self):
        report_path = self.output_dir / f"renaming_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_path, 'w') as f:
            f.write(f"Combined Camera Renaming Report\n")
            f.write(f"=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total entries processed: {len(self.all_files)}\n")
            f.write(f"Output directory: {self.output_dir}\n")
            f.write(f"Action performed: {'Move' if self.move_files else 'Copy'}\n")
            f.write(f"=" * 80 + "\n")
            f.write(f"FILE RENAMING DETAILS\n")
            f.write(f"-" * 80 + "\n\n")
            
            for idx, file_entry in enumerate(self.all_files, 1):
                padded_seq = str(idx).zfill(4) if idx < 10000 else str(idx)
                timestamp_str = file_entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                
                f.write(f"[{idx:5d}] CAM{file_entry['camera']} | {timestamp_str}\n")
                
                if file_entry['jpg_path']:
                    f.write(f"  JPG Original: {file_entry['jpg_path'].name}\n")
                    f.write(f"  JPG New: DSCF{padded_seq}.JPG\n")
                
                if file_entry['raw_path']:
                    raw_ext = file_entry['raw_path'].suffix.upper()
                    f.write(f"  RAW Original: {file_entry['raw_path'].name}\n")
                    f.write(f"  RAW New: DSCF{padded_seq}{raw_ext}\n")
                
                f.write("\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraRenamerGUI(root)
    root.mainloop()
