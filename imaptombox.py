#!/usr/bin/env python3
"""
IMAP Email Downloader and mbox Converter
---------------------------------------
This application downloads all emails from an IMAP account to a local PC
and provides an option to convert them to mbox format.
Optimized for very large mailboxes (100GB+).
by Denis (BeforeMyCompileFails) 2025
"""

import argparse
import email
import imaplib
import json
import mailbox
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from getpass import getpass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re


# Increase the imaplib size limit to handle large responses
# Default is 10000 bytes, increase to 100MB
imaplib._MAXLINE = 100000000


class IMAPDownloader:
    """Manages the download of emails from an IMAP server to local storage."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 993,
        use_ssl: bool = True,
        output_dir: str = "emails",
        debug: bool = False,
        batch_size: int = 1000,
    ):
        """Initialize the IMAP downloader with connection parameters."""
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.output_dir = Path(output_dir)
        self.connection = None
        self.metadata = {}
        self.metadata_file = self.output_dir / "metadata.json"
        self.debug = debug
        self.batch_size = batch_size
        
        # Create output directory and ensure it exists
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"Output directory: {os.path.abspath(self.output_dir)}")
        except Exception as e:
            print(f"Error creating output directory: {e}")
            print(f"Current working directory: {os.getcwd()}")
            raise

    def debug_print(self, message: str) -> None:
        """Print debug messages if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def connect(self) -> bool:
        """Establish connection to the IMAP server."""
        try:
            print(f"Connecting to {self.host}:{self.port} (SSL: {self.use_ssl})...")
            
            if self.use_ssl:
                self.debug_print("Using IMAP4_SSL")
                self.connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self.debug_print("Using IMAP4")
                self.connection = imaplib.IMAP4(self.host, self.port)
            
            self.debug_print("Connection established, attempting login...")
            self.connection.login(self.username, self.password)
            print(f"Connected to {self.host} as {self.username}")
            return True
        except imaplib.IMAP4.error as e:
            print(f"IMAP4 error: {e}")
            return False
        except ConnectionRefusedError:
            print(f"Connection refused to {self.host}:{self.port}")
            return False
        except OSError as e:
            print(f"Network error: {e}")
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            if self.debug:
                traceback.print_exc()
            return False

    def disconnect(self) -> None:
        """Close the connection to the IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
                print("Disconnected from IMAP server")
            except Exception as e:
                print(f"Error during disconnect: {e}")

    def get_folders(self) -> List[str]:
        """Get a list of all folders in the IMAP account."""
        if not self.connection:
            print("Not connected to IMAP server")
            return []

        folders = []
        try:
            # First try listing all mailboxes
            self.debug_print("Fetching folder list...")
            
            # Try namespace method first
            try:
                result, namespaces = self.connection.namespace()
                if result == "OK" and namespaces and namespaces[0]:
                    self.debug_print(f"Namespace response: {namespaces}")
            except Exception as e:
                self.debug_print(f"Namespace command failed: {e}")
            
            # List all mailboxes
            result, folder_list = self.connection.list()
            
            if result != "OK":
                print(f"Failed to retrieve folders: {result}")
                
                # Fallback: Try to list INBOX explicitly
                self.debug_print("Attempting fallback to list INBOX only")
                try:
                    result, inbox_list = self.connection.list('', 'INBOX')
                    if result == "OK" and inbox_list and inbox_list[0]:
                        folder_list = inbox_list
                    else:
                        # Second fallback: Just use INBOX
                        folders = ["INBOX"]
                        print("Using INBOX as default folder")
                        return folders
                except Exception as e:
                    self.debug_print(f"Inbox list fallback failed: {e}")
                    folders = ["INBOX"]
                    return folders

            if not folder_list:
                print("No folders returned from server")
                folders = ["INBOX"]  # Default to INBOX
                return folders
                
            self.debug_print(f"Raw folder list: {folder_list}")
            
            # Process the folder list
            for folder_info in folder_list:
                try:
                    # Decode the folder information
                    decoded_info = folder_info.decode("utf-8")
                    self.debug_print(f"Decoded folder info: {decoded_info}")
                    
                    # Skip folders that look like dots or are empty
                    if decoded_info.endswith(' "."') or decoded_info.endswith(' .'):
                        self.debug_print("Skipping dot folder")
                        continue
                    
                    # Extract folder name using regex
                    # Look for quoted pattern
                    match = re.search(r'"([^"]*)"$', decoded_info)
                    if match:
                        folder_name = match.group(1)
                    else:
                        # Look for unquoted pattern at end
                        match = re.search(r' ([^ "]+)$', decoded_info)
                        if match:
                            folder_name = match.group(1)
                        else:
                            # Last resort: take the last part
                            parts = decoded_info.split()
                            folder_name = parts[-1].strip('"')
                    
                    # Skip dot folders
                    if folder_name == "." or folder_name == "..":
                        continue
                    
                    # Add to folder list
                    if folder_name not in folders:  # Avoid duplicates
                        folders.append(folder_name)
                        self.debug_print(f"Added folder: {folder_name}")
                    
                except Exception as e:
                    print(f"Error parsing folder info {folder_info}: {e}")
                    if self.debug:
                        traceback.print_exc()
                    continue
            
            # If no folders were found, use INBOX as a fallback
            if not folders:
                folders = ["INBOX"]
                print("No valid folders found. Using INBOX as default folder.")
                
            print(f"Found {len(folders)} folders: {', '.join(folders)}")
            return folders
            
        except Exception as e:
            print(f"Error getting folders: {e}")
            if self.debug:
                traceback.print_exc()
                
            # Fallback to default INBOX
            folders = ["INBOX"]
            print("Using INBOX as default folder due to error")
            return folders

    def download_emails(
        self, 
        folders: Optional[List[str]] = None, 
        max_emails: Optional[int] = None,
        skip_existing: bool = True,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        start_message: int = 1
    ) -> Dict[str, int]:
        """Download emails from specified folders or all folders."""
        if not self.connection:
            print("Not connected to IMAP server")
            return {}

        if not folders:
            folders = self.get_folders()
            
        if not folders:
            print("No folders to download from, defaulting to INBOX")
            folders = ["INBOX"]  # Default fallback
            
        # Load existing metadata if available
        self._load_metadata()
            
        download_stats = {}
        
        for folder_name in folders:
            try:
                print(f"\nAttempting to select folder: '{folder_name}'")
                
                # Select the folder - try different variations
                selected = False
                variations = [
                    lambda: self.connection.select(f'"{folder_name}"', readonly=True),  # Quoted
                    lambda: self.connection.select(folder_name, readonly=True),         # Unquoted
                    lambda: self.connection.select(folder_name.encode('utf-7'), readonly=True),  # UTF-7 encoded
                ]
                
                for select_method in variations:
                    try:
                        result, data = select_method()
                        if result == "OK":
                            selected = True
                            break
                    except Exception as e:
                        self.debug_print(f"Selection attempt failed: {e}")
                
                if not selected:
                    print(f"Failed to select folder '{folder_name}'. Skipping.")
                    continue
                
                if not data or not data[0]:
                    print(f"No data returned when selecting folder '{folder_name}'")
                    continue
                    
                try:
                    msg_count = int(data[0])
                    print(f"Processing folder '{folder_name}' ({msg_count} messages)")
                except (ValueError, TypeError) as e:
                    print(f"Invalid message count for folder '{folder_name}': {data[0]}")
                    print(f"Error: {e}")
                    continue
                
                # Create folder directory
                folder_dir = self._get_safe_path(self.output_dir / folder_name)
                os.makedirs(folder_dir, exist_ok=True)
                print(f"Saving to directory: {os.path.abspath(folder_dir)}")
                
                # Initialize folder in metadata if needed
                if folder_name not in self.metadata:
                    self.metadata[folder_name] = {"downloaded": [], "last_uid": 0, "last_message_id": 0}
                
                # For large mailboxes, fetch emails in batches
                # If no start_message is specified, use the last processed message ID + 1
                if start_message == 1 and self.metadata[folder_name].get("last_message_id", 0) > 0:
                    start_message = self.metadata[folder_name]["last_message_id"] + 1
                
                # Process messages in batches
                total_downloaded = 0
                batch_start = start_message
                
                while batch_start <= msg_count:
                    batch_end = min(batch_start + self.batch_size - 1, msg_count)
                    
                    if max_emails and total_downloaded >= max_emails:
                        print(f"Reached maximum number of emails to download ({max_emails})")
                        break
                    
                    # Calculate remaining emails to download if max_emails is set
                    remaining = None
                    if max_emails:
                        remaining = max_emails - total_downloaded
                        if remaining <= 0:
                            break
                        if remaining < (batch_end - batch_start + 1):
                            batch_end = batch_start + remaining - 1
                    
                    print(f"\nProcessing batch {batch_start}-{batch_end} of {msg_count} messages")
                    
                    # Create search criteria for this batch
                    # For very large mailboxes, search by message sequence numbers instead of ALL
                    batch_range = f"{batch_start}:{batch_end}"
                    
                    try:
                        # Fetch message IDs for this batch instead of searching
                        # This avoids the large response issue with SEARCH
                        batch_ids = list(range(batch_start, batch_end + 1))
                        batch_ids_str = [str(i) for i in batch_ids]
                        
                        # Process each message in the batch
                        batch_downloaded = 0
                        
                        for i, message_id in enumerate(batch_ids):
                            message_id_str = str(message_id)
                            
                            try:
                                # Fetch UID first
                                result, uid_data = self.connection.fetch(message_id_str, "(UID)")
                                if result != "OK" or not uid_data or not uid_data[0]:
                                    self.debug_print(f"Failed to fetch UID for message {message_id_str}")
                                    continue
                                
                                uid_str = uid_data[0].decode("utf-8")
                                self.debug_print(f"UID data: {uid_str}")
                                
                                # Extract UID
                                uid_match = re.search(r'UID (\d+)', uid_str)
                                if uid_match:
                                    uid = int(uid_match.group(1))
                                else:
                                    # Fallback - use message ID
                                    uid = message_id
                                
                                # Skip if already downloaded
                                if skip_existing and uid in self.metadata[folder_name]["downloaded"]:
                                    if (i + 1) % 10 == 0 or i == len(batch_ids) - 1:
                                        print(f"Processed {i+1}/{len(batch_ids)} messages in batch (skipped existing)", end="\r")
                                    continue
                                
                                # Fetch the message
                                result, msg_data = self.connection.fetch(message_id_str, "(RFC822)")
                                
                                if result != "OK" or not msg_data or not msg_data[0] or len(msg_data[0]) < 2:
                                    print(f"Failed to fetch message {message_id_str}")
                                    continue
                                
                                # Parse the email
                                raw_email = msg_data[0][1]
                                email_message = email.message_from_bytes(raw_email)
                                
                                # Get subject for filename
                                subject = email_message.get("Subject", "No Subject")
                                
                                # Clean subject for filename
                                clean_subject = "".join(c if c.isalnum() else "_" for c in subject)
                                clean_subject = clean_subject[:50]  # Limit length
                                
                                # Create filename with UID to ensure uniqueness
                                filename = f"{uid}_{clean_subject}.eml"
                                file_path = folder_dir / filename
                                
                                # Save the email
                                with open(file_path, "wb") as f:
                                    f.write(raw_email)
                                
                                # Update metadata
                                if uid not in self.metadata[folder_name]["downloaded"]:
                                    self.metadata[folder_name]["downloaded"].append(uid)
                                
                                if uid > self.metadata[folder_name].get("last_uid", 0):
                                    self.metadata[folder_name]["last_uid"] = uid
                                
                                # Update last message ID
                                self.metadata[folder_name]["last_message_id"] = message_id
                                
                                batch_downloaded += 1
                                total_downloaded += 1
                                
                                # Save metadata periodically (every 10 emails)
                                if batch_downloaded % 10 == 0:
                                    self._save_metadata()
                                    print(f"Downloaded {batch_downloaded}/{len(batch_ids)} messages in current batch", end="\r")
                                
                                # Exit if we've reached max_emails
                                if max_emails and total_downloaded >= max_emails:
                                    break
                                
                            except Exception as e:
                                print(f"Error processing message {message_id_str}: {e}")
                                if self.debug:
                                    traceback.print_exc()
                        
                        print(f"\nDownloaded {batch_downloaded} new emails from batch {batch_start}-{batch_end}")
                        
                        # Move to next batch
                        batch_start = batch_end + 1
                        
                        # Save metadata after each batch
                        self._save_metadata()
                        
                    except Exception as e:
                        print(f"Error processing batch {batch_start}-{batch_end}: {e}")
                        if self.debug:
                            traceback.print_exc()
                        
                        # Move to next batch even if this one failed
                        batch_start = batch_end + 1
                
                print(f"Total downloaded from '{folder_name}': {total_downloaded} emails")
                download_stats[folder_name] = total_downloaded
                
            except Exception as e:
                print(f"Error processing folder '{folder_name}': {e}")
                if self.debug:
                    traceback.print_exc()
                continue
        
        return download_stats

    def _get_safe_path(self, path: Path) -> Path:
        """Create a filesystem-safe path from a folder name."""
        # Replace characters that are problematic in filenames
        invalid_chars = '\\/:*?"<>|'
        safe_path_str = str(path)
        for char in invalid_chars:
            safe_path_str = safe_path_str.replace(char, '_')
        return Path(safe_path_str)

    def _load_metadata(self) -> None:
        """Load metadata from JSON file if it exists."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r") as f:
                    self.metadata = json.load(f)
                print(f"Loaded metadata from {self.metadata_file}")
            except Exception as e:
                print(f"Error loading metadata: {e}")
                if self.debug:
                    traceback.print_exc()
                self.metadata = {}
        else:
            print("No existing metadata found. Creating new metadata.")
            self.metadata = {}

    def _save_metadata(self) -> None:
        """Save metadata to JSON file."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
            self.debug_print(f"Saved metadata to {self.metadata_file}")
        except Exception as e:
            print(f"Error saving metadata: {e}")
            if self.debug:
                traceback.print_exc()


class MboxConverter:
    """Converts downloaded emails to mbox format."""
    
    def __init__(self, email_dir: str, debug: bool = False):
        """Initialize the converter."""
        self.email_dir = Path(email_dir)
        self.debug = debug
        
    def debug_print(self, message: str) -> None:
        """Print debug messages if debug mode is enabled."""
        if self.debug:
            print(f"[DEBUG] {message}")
        
    def convert_to_mbox(self, folder_name: Optional[str] = None, output_file: Optional[str] = None) -> str:
        """Convert downloaded emails to mbox format."""
        if not self.email_dir.exists():
            print(f"Email directory not found: {self.email_dir}")
            print(f"Current working directory: {os.getcwd()}")
            raise FileNotFoundError(f"Email directory {self.email_dir} not found")
        
        folders_to_convert = []
        
        if folder_name:
            folder_path = self._get_safe_path(self.email_dir / folder_name)
            if folder_path.exists() and folder_path.is_dir():
                folders_to_convert.append((folder_name, folder_path))
            else:
                print(f"Folder not found: {folder_path}")
                print(f"Available directories in {self.email_dir}:")
                for item in self.email_dir.iterdir():
                    if item.is_dir():
                        print(f"  - {item.name}")
                raise FileNotFoundError(f"Folder {folder_name} not found in {self.email_dir}")
        else:
            # Convert all folders
            print(f"Scanning for folders in {self.email_dir}")
            folders_found = False
            for path in self.email_dir.iterdir():
                if path.is_dir() and path.name != "__pycache__" and path.name != "metadata.json":
                    print(f"Found folder: {path.name}")
                    folders_to_convert.append((path.name, path))
                    folders_found = True
            
            # If no folders found, create mbox from .eml files in the root directory
            if not folders_found:
                eml_files = list(self.email_dir.glob("*.eml"))
                if eml_files:
                    print(f"No folders found, but {len(eml_files)} .eml files found in root directory")
                    folders_to_convert.append(("root", self.email_dir))
        
        if not folders_to_convert:
            # Last resort: Check if metadata.json exists and create empty folders
            if (self.email_dir / "metadata.json").exists():
                try:
                    with open(self.email_dir / "metadata.json", "r") as f:
                        metadata = json.load(f)
                    
                    # Create folders from metadata
                    for folder_name in metadata.keys():
                        folder_path = self._get_safe_path(self.email_dir / folder_name)
                        os.makedirs(folder_path, exist_ok=True)
                        print(f"Created folder from metadata: {folder_name}")
                        folders_to_convert.append((folder_name, folder_path))
                except Exception as e:
                    print(f"Error processing metadata: {e}")
            
            if not folders_to_convert:
                print(f"No folders found to convert in {self.email_dir}")
                # Create empty mbox file anyway
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if output_file:
                    mbox_path = Path(output_file)
                else:
                    mbox_path = self.email_dir / f"empty_emails_{timestamp}.mbox"
                
                print(f"Creating empty mbox file: {mbox_path}")
                try:
                    mbox = mailbox.mbox(str(mbox_path))
                    mbox.flush()
                    return str(mbox_path)
                except Exception as e:
                    print(f"Error creating empty mbox: {e}")
                    raise
        
        # Determine output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file:
            mbox_path = Path(output_file)
        else:
            if folder_name:
                mbox_path = self.email_dir / f"{folder_name}_{timestamp}.mbox"
            else:
                mbox_path = self.email_dir / f"all_emails_{timestamp}.mbox"
        
        print(f"Creating mbox file: {mbox_path}")
        
        # Create mbox file
        try:
            mbox = mailbox.mbox(str(mbox_path))
            mbox.lock()
        except Exception as e:
            print(f"Error creating mbox file: {e}")
            if self.debug:
                traceback.print_exc()
            raise
        
        try:
            total_emails = 0
            
            for name, folder_path in folders_to_convert:
                print(f"Converting folder '{name}'...")
                converted = 0
                
                # Get all .eml files in the folder
                email_files = list(folder_path.glob("*.eml"))
                file_count = len(email_files)
                print(f"Found {file_count} .eml files in {folder_path}")
                
                # Process in batches to avoid memory issues with large folders
                batch_size = 1000
                for batch_start in range(0, file_count, batch_size):
                    batch_end = min(batch_start + batch_size, file_count)
                    batch_files = email_files[batch_start:batch_end]
                    
                    for email_file in batch_files:
                        try:
                            with open(email_file, "rb") as f:
                                email_content = f.read()
                            
                            # Parse email content
                            email_message = email.message_from_bytes(email_content)
                            
                            # Add to mbox
                            mbox.add(email_message)
                            converted += 1
                            
                            # Show progress
                            if converted % 100 == 0:
                                print(f"Converted {converted}/{file_count} emails from '{name}'", end="\r")
                        
                        except Exception as e:
                            print(f"Error converting {email_file}: {e}")
                            if self.debug:
                                traceback.print_exc()
                    
                    # Flush to disk after each batch to save memory
                    mbox.flush()
                
                print(f"\nConverted {converted} emails from '{name}'")
                total_emails += converted
            
            mbox.flush()
            print(f"\nTotal of {total_emails} emails converted to {mbox_path}")
            return str(mbox_path)
            
        except Exception as e:
            print(f"Error during conversion: {e}")
            if self.debug:
                traceback.print_exc()
            raise
        finally:
            try:
                mbox.unlock()
            except Exception:
                pass
    
    def _get_safe_path(self, path: Path) -> Path:
        """Create a filesystem-safe path from a folder name."""
        # Replace characters that are problematic in filenames
        invalid_chars = '\\/:*?"<>|'
        safe_path_str = str(path)
        for char in invalid_chars:
            safe_path_str = safe_path_str.replace(char, '_')
        return Path(safe_path_str)


def main():
    """Main function to parse arguments and run the application."""
    parser = argparse.ArgumentParser(
        description="Download emails from IMAP and optionally convert to mbox format"
    )
    
    # Connection parameters
    parser.add_argument("--host", help="IMAP server hostname", required=True)
    parser.add_argument("--port", type=int, default=993, help="IMAP server port (default: 993)")
    parser.add_argument("--username", help="Email account username", required=True)
    parser.add_argument("--no-ssl", action="store_true", help="Disable SSL (not recommended)")
    
    # Download parameters
    parser.add_argument(
        "--output-dir", 
        default="emails", 
        help="Directory to save emails (default: emails)"
    )
    parser.add_argument(
        "--folders", 
        nargs="+", 
        help="Specific folders to download (default: all folders)"
    )
    parser.add_argument(
        "--max-emails", 
        type=int,
        help="Maximum number of emails to download per folder"
    )
    parser.add_argument(
        "--download-all", 
        action="store_true", 
        help="Force download of all emails, even if already downloaded"
    )
    
    # Large mailbox handling
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of emails to process in a single batch (default: 1000)"
    )
    parser.add_argument(
        "--start-message",
        type=int,
        default=1,
        help="Message ID to start downloading from (default: 1)"
    )
    
    # Force INBOX only mode
    parser.add_argument(
        "--inbox-only",
        action="store_true",
        help="Only download from INBOX folder"
    )
    
    # Conversion parameters
    parser.add_argument(
        "--convert", 
        action="store_true", 
        help="Convert downloaded emails to mbox format"
    )
    parser.add_argument(
        "--convert-folder", 
        help="Specific folder to convert to mbox (default: all folders)"
    )
    parser.add_argument(
        "--mbox-file", 
        help="Custom output file name for mbox conversion"
    )
    
    # Skip download (only convert)
    parser.add_argument(
        "--skip-download", 
        action="store_true", 
        help="Skip download and only perform conversion"
    )
    
    # Debug mode
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug output"
    )
    
    args = parser.parse_args()
    
    # Print script information
    print("=" * 60)
    print("IMAP Email Downloader and mbox Converter")
    print("=" * 60)
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script file: {os.path.abspath(__file__)}")
    print("-" * 60)
    
    # If neither download nor convert is specified, enable both
    if not args.skip_download and not args.convert:
        args.convert = True  # Default behavior: download and convert
    
    # Handle inbox-only mode
    if args.inbox_only:
        args.folders = ["INBOX"]
        print("Inbox-only mode: Will only process the INBOX folder")
    
    # Get password securely
    password = getpass(f"Enter password for {args.username}: ")
    
    # Download emails
    if not args.skip_download:
        downloader = IMAPDownloader(
            host=args.host,
            username=args.username,
            password=password,
            port=args.port,
            use_ssl=not args.no_ssl,
            output_dir=args.output_dir,
            debug=args.debug,
            batch_size=args.batch_size
        )
        
        if downloader.connect():
            try:
                downloader.download_emails(
                    folders=args.folders, 
                    max_emails=args.max_emails,
                    skip_existing=not args.download_all,
                    start_message=args.start_message
                )
            except Exception as e:
                print(f"Error during download: {e}")
                if args.debug:
                    traceback.print_exc()
                sys.exit(1)
            finally:
                downloader.disconnect()
        else:
            sys.exit(1)
    
    # Convert to mbox
    if args.convert:
        try:
            converter = MboxConverter(email_dir=args.output_dir, debug=args.debug)
            mbox_file = converter.convert_to_mbox(
                folder_name=args.convert_folder,
                output_file=args.mbox_file
            )
            print(f"Conversion complete. MBOX file: {mbox_file}")
        except Exception as e:
            print(f"Error during mbox conversion: {e}")
            if args.debug:
                traceback.print_exc()
            sys.exit(1)
    
    print("\nDone!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("For debugging, run with --debug option")
        traceback.print_exc()
        sys.exit(1)