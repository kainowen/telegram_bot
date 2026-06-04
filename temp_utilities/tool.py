import os
import shutil
import datetime

def archive_old_downloads(source_dir="~/Downloads"):
    """
    Moves files older than 30 days from the source directory 
    to an archive subdirectory within the source directory.
    """
    # Expand user home directory path
    source_dir = os.path.expanduser(source_dir)
    
    # Define the archive directory path
    archive_dir = os.path.join(source_dir, "Archive")
    
    # Create the archive directory if it doesn't exist
    os.makedirs(archive_dir, exist_ok=True)
    
    # Calculate the cutoff time (30 days ago)
    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=30)
    
    print(f"Checking for files in: {source_dir}")
    print(f"Archiving files older than: {cutoff_time.strftime('%Y-%m-%d')}")
    
    files_moved_count = 0
    
    # Iterate over all items in the source directory
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        
        # Skip directories (including the Archive directory itself)
        if os.path.isdir(file_path):
            if file_path == os.path.join(source_dir, "Archive"):
                continue
            # Optional: Skip other subdirectories if needed
            continue

        try:
            # Get the last modification time (mtime)
            mod_timestamp = os.path.getmtime(file_path)
            mod_datetime = datetime.datetime.fromtimestamp(mod_timestamp)
            
            # Check if the file is older than the cutoff time
            if mod_datetime < cutoff_time:
                destination_path = os.path.join(archive_dir, filename)
                
                # Handle potential name collisions in the archive
                if os.path.exists(destination_path):
                    print(f"Skipping {filename}: Already exists in archive.")
                    continue
                
                # Move the file
                shutil.move(file_path, destination_path)
                print(f"Moved: {filename} -> Archive/")
                files_moved_count += 1
        
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    print("-" * 30)
    print(f"Finished. Total files moved: {files_moved_count}")

if __name__ == "__main__":
    archive_old_downloads()