"""
File Watcher Service

Monitors the docs folder for changes and automatically updates the knowledge base
using background job processing for efficient real-time documentation sync.
"""

from typing import Dict, List, Optional, Set, Callable, Any
import asyncio
import os
import logging
from datetime import datetime
from pathlib import Path
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from app.services.background_job_service import background_job_service, JobPriority

logger = logging.getLogger(__name__)


class FileWatcherService:
    """
    File Watcher Service for Automatic Knowledge Base Updates
    
    Features:
    - Real-time monitoring of docs folder
    - Automatic knowledge base updates via background jobs
    - File change detection and deduplication
    - Efficient polling with minimal resource usage
    """
    
    def __init__(self):
        self.docs_path = Path("/Users/ferdousazad/Documents/erp-suite/erp-ai-copilot/docs")
        self.erp_docs_path = Path("/Users/ferdousazad/Documents/erp-suite/erp-suit-technical-docs")
        self.file_hashes: Dict[str, str] = {}
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.check_interval = 30  # seconds
        
    async def start_monitoring(self):
        """Start file monitoring"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_files())
        logger.info("File watcher service started")
    
    async def stop_monitoring(self):
        """Stop file monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("File watcher service stopped")
    
    async def _monitor_files(self):
        """Main file monitoring loop"""
        # Initial scan
        await self._scan_and_update_files()
        
        while self.is_monitoring:
            try:
                await asyncio.sleep(self.check_interval)
                await self._scan_and_update_files()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"File monitoring error: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _scan_and_update_files(self):
        """Scan directories and update knowledge base for changed files"""
        try:
            # Scan AI copilot docs
            await self._scan_directory(self.docs_path, "ai_copilot_docs")
            
            # Scan ERP technical docs
            if self.erp_docs_path.exists():
                await self._scan_directory(self.erp_docs_path, "erp_technical_docs")
            
        except Exception as e:
            logger.error(f"File scan error: {e}")
    
    async def _scan_directory(self, directory: Path, category: str):
        """Scan a directory for markdown file changes"""
        if not directory.exists():
            return
        
        for md_file in directory.rglob("*.md"):
            if md_file.is_file():
                await self._check_file_changes(md_file, category)
    
    async def _check_file_changes(self, file_path: Path, category: str):
        """Check if file has changed and schedule update if needed"""
        try:
            file_str = str(file_path)
            
            # Calculate file hash
            with open(file_path, 'rb') as f:
                file_content = f.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check if file is new or modified
            if file_str not in self.file_hashes or self.file_hashes[file_str] != file_hash:
                logger.info(f"File change detected: {file_path.name}")
                
                # Handle file change
                await self.handle_file_change(file_str, "modified")
                
                # Schedule background job to update knowledge base
                await background_job_service.schedule_job(
                    job_type="process_documentation_update",
                    function_name="process_new_documentation",
                    args=[file_str],
                    priority=JobPriority.MEDIUM,
                    metadata={
                        "file_path": file_str,
                        "category": category,
                        "change_type": "new" if file_str not in self.file_hashes else "modified",
                        "file_hash": file_hash
                    }
                )
                
                # Update hash
                self.file_hashes[file_str] = file_hash
                
        except Exception as e:
            logger.error(f"Error checking file changes: {e}")

    async def handle_file_change(self, file_path: str, change_type: str):
        """Handle file change event"""
        try:
            logger.info(f"File change detected: {file_path} ({change_type})")
            
            # Calculate file hash
            file_hash = await self._calculate_file_hash(file_path)
            
            # Check if file actually changed
            if file_path in self.file_hashes and self.file_hashes[file_path] == file_hash:
                return  # No actual change
            
            # Update hash
            self.file_hashes[file_path] = file_hash
            
            # Schedule background job for knowledge base update
            if hasattr(self, 'background_job_service'):
                await self.background_job_service.schedule_job(
                    job_type="process_new_documentation",
                    data={
                        "file_path": file_path,
                        "change_type": change_type,
                        "file_hash": file_hash
                    },
                    priority=1
                )
            
            logger.info(f"Scheduled knowledge base update for: {file_path}")
            
        except Exception as e:
            logger.error(f"Error handling file change: {e}")

    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash for {file_path}: {e}")
            return ""

    async def force_rescan(self):
        """Force a complete rescan of all directories"""
        logger.info("Starting force rescan of documentation files")
        self.file_hashes.clear()
        await self._scan_and_update_files()
        logger.info("Force rescan completed")
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Get file monitoring status"""
        return {
            "is_monitoring": self.is_monitoring,
            "monitored_files": len(self.file_hashes),
            "docs_path": str(self.docs_path),
            "erp_docs_path": str(self.erp_docs_path),
            "check_interval": self.check_interval,
            "last_scan": datetime.utcnow().isoformat()
        }


# Global file watcher service instance
file_watcher_service = FileWatcherService()
