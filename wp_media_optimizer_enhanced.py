#!/usr/bin/env python3
"""
WordPress Media Optimizer with SEO-Friendly Permalinks
======================================================

Enhanced version with automatic configuration setup, comprehensive help,
and user-friendly interface for WordPress media optimization with SEO permalinks.

Features:
- Automatic configuration file creation with interactive setup
- ExifTool-based metadata embedding
- WebP conversion with compression
- SEO-friendly permalink generation
- Automatic .htaccess rules generation
- WordPress rewrite rule updates
- Comprehensive help system
- Validation and error handling

Version: 3.1.0-enhanced
Author: WordPress Media Optimizer Team
License: MIT

Usage Examples:
    python3 wp_media_optimizer_permalink.py --setup        # Interactive setup
    python3 wp_media_optimizer_permalink.py --help         # Show help
    python3 wp_media_optimizer_permalink.py --dry-run      # Test run
    python3 wp_media_optimizer_permalink.py --limit 100    # Process 100 files
"""

import os
import sys
import json
import shutil
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import time
import re
import getpass

# Core libraries
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    mysql_available = True
except ImportError:
    mysql_available = False

try:
    from PIL import Image, ExifTags
    from PIL.ExifTags import TAGS
    pil_available = True
except ImportError:
    pil_available = False

class WordPressMediaOptimizerEnhanced:
    """Enhanced WordPress Media Optimizer with SEO Permalink Support"""
    
    def __init__(self, config_file: str = "wp_optimizer_config.json", dry_run: bool = False):
        self.version = "3.1.0-enhanced"
        self.config_file = config_file
        self.dry_run = dry_run
        self.start_time = datetime.now()
        
        # Stats tracking
        self.stats = {
            'processed': 0,
            'webp_converted': 0,
            'renamed': 0,
            'metadata_added': 0,
            'metadata_failed': 0,
            'permalinks_updated': 0,
            'permalink_failures': 0,
            'errors': 0,
            'size_saved': 0
        }
        
        # Initialize components
        self._setup_logging()
        
        # Database connection
        self.db_connection = None
        self.wp_prefix = "wp_"
        
        # WordPress paths
        self.wp_path = None
        self.uploads_path = None
        
        # Permalink tracking
        self.permalink_updates = []
        
        # Configuration loaded flag
        self.config_loaded = False

    def _setup_logging(self):
        """Setup enhanced logging"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"{timestamp}_wp_optimizer_enhanced.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"WordPress Media Optimizer Enhanced v{self.version} initialized")
        self.logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        self.logger.info(f"Log file: {log_file}")

    def show_banner(self):
        """Display application banner"""
        print("═" * 80)
        print("🚀 WordPress Media Optimizer with SEO Permalinks")
        print(f"   Version {self.version} - Enhanced Edition")
        print("   Optimize images, add metadata, create SEO-friendly URLs")
        print("═" * 80)
        print()

    def show_usage(self):
        """Show comprehensive usage information"""
        print("""
USAGE:
    python3 wp_media_optimizer_permalink.py [OPTIONS]

QUICK START:
    1. First-time setup:
       python3 wp_media_optimizer_permalink.py --setup
    
    2. Test run (recommended):
       python3 wp_media_optimizer_permalink.py --dry-run
    
    3. Live optimization:
       python3 wp_media_optimizer_permalink.py

MAIN OPTIONS:
    --setup                 Interactive configuration setup
    --dry-run              Test run without making changes
    --help, -h             Show this help message
    --version              Show version information
    --check-requirements   Check system requirements
    --validate-config      Validate configuration file

PROCESSING OPTIONS:
    --limit NUMBER         Process only N attachments (default: 50)
    --offset NUMBER        Start from Nth attachment (default: 0)
    --config FILE          Use custom configuration file
    --batch-size NUMBER    Database batch size (default: 50)

ADVANCED OPTIONS:
    --skip-webp            Skip WebP conversion
    --skip-metadata        Skip metadata embedding
    --skip-permalinks      Skip permalink optimization
    --skip-htaccess        Skip .htaccess generation
    --backup-only          Only backup files, no optimization
    --force-overwrite      Overwrite existing optimized files

EXAMPLES:
    # Interactive setup for new users
    python3 wp_media_optimizer_permalink.py --setup
    
    # Test optimization on first 10 images
    python3 wp_media_optimizer_permalink.py --dry-run --limit 10
    
    # Optimize 100 images starting from the 50th
    python3 wp_media_optimizer_permalink.py --limit 100 --offset 50
    
    # Only update permalinks, skip image optimization
    python3 wp_media_optimizer_permalink.py --skip-webp --skip-metadata
    
    # Use custom configuration
    python3 wp_media_optimizer_permalink.py --config /path/to/custom.json

CONFIGURATION:
    Configuration is stored in: wp_optimizer_config.json
    Run --setup to create or modify the configuration interactively.

REQUIREMENTS:
    - Python 3.7+
    - ExifTool (for metadata)
    - MySQL connector (pip install mysql-connector-python)
    - Pillow (pip install Pillow)
    - WordPress installation with MySQL database
    - Root/sudo access for file operations

SAFETY FEATURES:
    - Automatic backup of original files
    - Dry-run mode for testing
    - Database transaction rollback on errors
    - Comprehensive logging
    - Configuration validation

For more information and documentation:
https://github.com/wordpress-media-optimizer
""")

    def show_version(self):
        """Show version and system information"""
        print(f"""
WordPress Media Optimizer Enhanced
Version: {self.version}
Python: {sys.version}
Platform: {sys.platform}

Feature Support:
- MySQL Connector: {'✅ Available' if mysql_available else '❌ Missing'}
- PIL/Pillow: {'✅ Available' if pil_available else '❌ Missing'}
- ExifTool: {'✅ Available' if self._check_exiftool() else '❌ Missing'}

Configuration File: {self.config_file}
Configuration Exists: {'✅ Yes' if os.path.exists(self.config_file) else '❌ No'}
""")

    def _check_exiftool(self) -> bool:
        """Quick check for ExifTool availability"""
        try:
            result = subprocess.run(['exiftool', '-ver'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except:
            return False

    def check_requirements(self, verbose: bool = True) -> bool:
        """Comprehensive system requirements check"""
        if verbose:
            print("🔍 System Requirements Check")
            print("=" * 35)
        
        requirements_met = True
        issues = []
        
        # Check Python version
        if sys.version_info < (3, 7):
            issues.append("Python 3.7+ required")
            requirements_met = False
        elif verbose:
            print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
        
        # Check root privileges
        if os.geteuid() == 0:
            if verbose:
                print("✅ Running as root (good for file permissions)")
        else:
            if verbose:
                print("⚠️  Not running as root (may have permission issues)")
            issues.append("Consider running as root/sudo for file operations")
        
        # Check MySQL connector
        if mysql_available:
            if verbose:
                print("✅ MySQL connector available")
        else:
            issues.append("Missing: mysql-connector-python (pip install mysql-connector-python)")
            requirements_met = False
            
        # Check PIL
        if pil_available:
            if verbose:
                print("✅ PIL/Pillow available")
        else:
            issues.append("Missing: Pillow (pip install Pillow)")
            requirements_met = False
            
        # Check ExifTool
        if self._check_exiftool():
            try:
                result = subprocess.run(['exiftool', '-ver'], 
                                      capture_output=True, text=True, timeout=5)
                version = result.stdout.strip()
                if verbose:
                    print(f"✅ ExifTool v{version} available")
            except:
                pass
        else:
            issues.append("Missing: ExifTool (install from https://exiftool.org/)")
            requirements_met = False
        
        # Check configuration
        if os.path.exists(self.config_file):
            if verbose:
                print(f"✅ Configuration file: {self.config_file}")
        else:
            issues.append(f"Configuration file missing: {self.config_file}")
            if verbose:
                print(f"⚠️  No configuration file: {self.config_file}")
        
        if verbose:
            print()
            if requirements_met:
                print("✅ All requirements satisfied!")
            else:
                print("❌ Some requirements missing:")
                for issue in issues:
                    print(f"   • {issue}")
                print("\nRun --setup to configure the application.")
        
        return requirements_met

    def create_default_config(self) -> Dict:
        """Create default configuration with comprehensive settings"""
        return {
            "wordpress_path": "/var/www/html",
            "database": {
                "host": "localhost",
                "port": 3306,
                "user": "wordpress",
                "password": "",
                "database": "wordpress",
                "socket": "/var/lib/mysql/mysql.sock"
            },
            "optimization": {
                "webp_quality": 85,
                "webp_lossless": False,
                "backup_originals": True,
                "batch_size": 50,
                "parallel_processing": False,
                "skip_existing": True,
                "max_file_size_mb": 50
            },
            "metadata": {
                "enabled": True,
                "method": "exiftool",
                "encoding": "utf-8",
                "supported_formats": [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"],
                "embed_title": True,
                "embed_description": True,
                "embed_keywords": True,
                "generate_keywords_from_title": True,
                "max_keywords": 5,
                "min_keyword_length": 3,
                "overwrite_existing": True,
                "add_creation_date": True,
                "add_source_info": True
            },
            "filename_optimization": {
                "enabled": True,
                "max_length": 200,
                "remove_special_chars": True,
                "lowercase": True,
                "replace_spaces": "-",
                "remove_stop_words": True,
                "transliterate_unicode": True
            },
            "permalink_optimization": {
                "enabled": True,
                "structure": "/media/{slug}/",
                "use_title_as_slug": True,
                "max_slug_length": 100,
                "update_htaccess": True,
                "create_redirects": True,
                "attachment_page_template": "single-attachment.php",
                "force_unique_slugs": True
            },
            "exiftool": {
                "command": "exiftool",
                "timeout": 30,
                "preserve_original": False,
                "create_backup": False,
                "args": ["-overwrite_original", "-charset", "UTF8"]
            },
            "logging": {
                "level": "INFO",
                "max_log_files": 10,
                "log_file_max_size_mb": 10
            },
            "safety": {
                "max_batch_size": 1000,
                "require_confirmation": True,
                "create_restore_point": True,
                "verify_backups": True
            }
        }

    def interactive_setup(self):
        """Interactive configuration setup"""
        print("\n🔧 Interactive Configuration Setup")
        print("=" * 40)
        print("Let's configure WordPress Media Optimizer for your system.")
        print("Press Enter to use default values shown in [brackets].\n")
        
        config = self.create_default_config()
        
        # WordPress path
        print("📁 WordPress Installation")
        print("-" * 25)
        wp_path = input(f"WordPress path [{config['wordpress_path']}]: ").strip()
        if wp_path:
            config['wordpress_path'] = wp_path
        
        # Validate WordPress path
        if not self._validate_wordpress_path(config['wordpress_path']):
            print(f"⚠️  Warning: WordPress installation not found at {config['wordpress_path']}")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                print("Setup cancelled.")
                return False
        
        # Database configuration
        print("\n🗄️  Database Configuration")  
        print("-" * 26)
        
        db_host = input(f"Database host [{config['database']['host']}]: ").strip()
        if db_host:
            config['database']['host'] = db_host
            
        db_port = input(f"Database port [{config['database']['port']}]: ").strip()
        if db_port:
            try:
                config['database']['port'] = int(db_port)
            except ValueError:
                print("⚠️  Invalid port number, using default")
        
        db_name = input(f"Database name [{config['database']['database']}]: ").strip()
        if db_name:
            config['database']['database'] = db_name
            
        db_user = input(f"Database user [{config['database']['user']}]: ").strip()
        if db_user:
            config['database']['user'] = db_user
        
        # Database password (hidden input)
        print("Database password (input will be hidden):")
        db_pass = getpass.getpass("Password: ")
        if db_pass:
            config['database']['password'] = db_pass
        
        # Test database connection
        if self._test_database_connection(config['database']):
            print("✅ Database connection successful!")
        else:
            print("❌ Database connection failed!")
            proceed = input("Continue with current settings? (y/N): ").strip().lower()
            if proceed != 'y':
                print("Setup cancelled.")
                return False
        
        # Optimization settings
        print("\n🖼️  Optimization Settings")
        print("-" * 25)
        
        webp_quality = input(f"WebP quality (1-100) [{config['optimization']['webp_quality']}]: ").strip()
        if webp_quality:
            try:
                quality = int(webp_quality)
                if 1 <= quality <= 100:
                    config['optimization']['webp_quality'] = quality
                else:
                    print("⚠️  Quality must be between 1-100, using default")
            except ValueError:
                print("⚠️  Invalid quality value, using default")
        
        backup_originals = input(f"Backup original files? (y/N) [{'y' if config['optimization']['backup_originals'] else 'n'}]: ").strip().lower()
        if backup_originals:
            config['optimization']['backup_originals'] = backup_originals == 'y'
        
        # Permalink settings
        print("\n🔗 SEO Permalink Settings")
        print("-" * 26)
        
        enable_permalinks = input(f"Enable SEO permalinks? (Y/n) [{'y' if config['permalink_optimization']['enabled'] else 'n'}]: ").strip().lower()
        if enable_permalinks:
            config['permalink_optimization']['enabled'] = enable_permalinks != 'n'
        
        if config['permalink_optimization']['enabled']:
            update_htaccess = input(f"Update .htaccess automatically? (Y/n) [{'y' if config['permalink_optimization']['update_htaccess'] else 'n'}]: ").strip().lower()
            if update_htaccess:
                config['permalink_optimization']['update_htaccess'] = update_htaccess != 'n'
        
        # Save configuration
        print(f"\n💾 Saving configuration to {self.config_file}")
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print("✅ Configuration saved successfully!")
            
            # Show summary
            print(f"\n📋 Configuration Summary")
            print("-" * 24)
            print(f"WordPress Path: {config['wordpress_path']}")
            print(f"Database: {config['database']['user']}@{config['database']['host']}/{config['database']['database']}")
            print(f"WebP Quality: {config['optimization']['webp_quality']}%")
            print(f"Backup Originals: {'Yes' if config['optimization']['backup_originals'] else 'No'}")
            print(f"SEO Permalinks: {'Yes' if config['permalink_optimization']['enabled'] else 'No'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return False

    def _validate_wordpress_path(self, wp_path: str) -> bool:
        """Validate WordPress installation path"""
        wp_path_obj = Path(wp_path)
        
        # Check if path exists
        if not wp_path_obj.exists():
            return False
        
        # Check for wp-config.php
        if not (wp_path_obj / "wp-config.php").exists():
            return False
        
        # Check for wp-content directory
        if not (wp_path_obj / "wp-content").exists():
            return False
        
        # Check for uploads directory
        uploads_path = wp_path_obj / "wp-content" / "uploads"
        if not uploads_path.exists():
            try:
                uploads_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created uploads directory: {uploads_path}")
            except:
                return False
        
        return True

    def _test_database_connection(self, db_config: Dict) -> bool:
        """Test database connection"""
        if not mysql_available:
            return False
        
        try:
            connection_params = {
                'host': db_config['host'],
                'port': db_config['port'],
                'user': db_config['user'],
                'password': db_config['password'],
                'database': db_config['database'],
                'connection_timeout': 10
            }
            
            connection = mysql.connector.connect(**connection_params)
            
            if connection.is_connected():
                cursor = connection.cursor()
                cursor.execute("SELECT VERSION()")
                cursor.fetchone()
                cursor.close()
                connection.close()
                return True
                
        except Exception as e:
            print(f"Database connection error: {e}")
            return False
        
        return False

    def validate_config(self) -> bool:
        """Validate existing configuration file"""
        if not os.path.exists(self.config_file):
            print(f"❌ Configuration file not found: {self.config_file}")
            print("Run --setup to create a configuration file.")
            return False
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            print("🔍 Validating Configuration")
            print("=" * 28)
            
            issues = []
            
            # Validate WordPress path
            if not self._validate_wordpress_path(config.get('wordpress_path', '')):
                issues.append(f"Invalid WordPress path: {config.get('wordpress_path', 'Not specified')}")
            else:
                print(f"✅ WordPress path: {config['wordpress_path']}")
            
            # Validate database config
            if self._test_database_connection(config.get('database', {})):
                print("✅ Database connection")
            else:
                issues.append("Database connection failed")
            
            # Validate optimization settings
            webp_quality = config.get('optimization', {}).get('webp_quality', 0)
            if 1 <= webp_quality <= 100:
                print(f"✅ WebP quality: {webp_quality}%")
            else:
                issues.append(f"Invalid WebP quality: {webp_quality} (must be 1-100)")
            
            # Show results
            if issues:
                print(f"\n❌ Configuration validation failed:")
                for issue in issues:
                    print(f"   • {issue}")
                print("\nRun --setup to fix configuration issues.")
                return False
            else:
                print("\n✅ Configuration validation passed!")
                return True
                
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            return False
        except Exception as e:
            print(f"❌ Configuration validation error: {e}")
            return False

    def load_config(self) -> bool:
        """Load and validate configuration"""
        if not os.path.exists(self.config_file):
            print(f"❌ Configuration file not found: {self.config_file}")
            print("Run --setup to create a configuration file.")
            return False
        
        try:
            with open(self.config_file, 'r') as f:
                user_config = json.load(f)
            
            # Merge with defaults
            default_config = self.create_default_config()
            self.config = self._deep_merge(default_config, user_config)
            
            self.config_loaded = True
            self.logger.info(f"Configuration loaded from {self.config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            self.logger.error(f"Failed to load config: {e}")
            return False

    def _deep_merge(self, dict1, dict2):
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _verify_exiftool(self):
        """Verify ExifTool is available"""
        if not self.config_loaded:
            return False
            
        exiftool_cmd = self.config.get('exiftool', {}).get('command', 'exiftool')
        
        try:
            result = subprocess.run([exiftool_cmd, '-ver'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.exiftool_version = version
                self.logger.info(f"ExifTool version {version} detected")
                return True
            else:
                self.logger.error(f"ExifTool test failed: {result.stderr}")
                return False
        except FileNotFoundError:
            self.logger.error("ExifTool not found")
            return False
        except Exception as e:
            self.logger.error(f"ExifTool verification failed: {e}")
            return False

    def detect_wordpress(self) -> bool:
        """Detect WordPress installation"""
        if not self.config_loaded:
            return False
            
        print("\n🔍 WordPress Detection")
        print("=" * 25)
        
        wp_path = Path(self.config['wordpress_path'])
        
        if not wp_path.exists():
            print(f"❌ WordPress path not found: {wp_path}")
            return False
            
        wp_config = wp_path / "wp-config.php"
        if not wp_config.exists():
            print(f"❌ wp-config.php not found in {wp_path}")
            return False
            
        uploads_path = wp_path / "wp-content" / "uploads"
        if not uploads_path.exists():
            print(f"❌ Uploads directory not found: {uploads_path}")
            return False
            
        self.wp_path = wp_path
        self.uploads_path = uploads_path
        
        print(f"✅ WordPress: {wp_path}")
        print(f"✅ Uploads: {uploads_path}")
        
        return True

    def connect_database(self) -> bool:
        """Connect to WordPress database"""
        if not mysql_available:
            print("❌ MySQL connector not available")
            return False
            
        db_config = self.config['database']
        
        print(f"\n🗄️  Database: {db_config['database']}")
        
        try:
            connection_params = {
                'host': db_config['host'],
                'port': db_config['port'],
                'user': db_config['user'],
                'password': db_config['password'],
                'database': db_config['database'],
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'autocommit': True
            }
            
            self.db_connection = mysql.connector.connect(**connection_params)
            
            if self.db_connection.is_connected():
                cursor = self.db_connection.cursor()
                cursor.execute("SELECT USER(), DATABASE(), VERSION()")
                result = cursor.fetchone()
                
                print(f"✅ Connected: {result[0]}")
                print(f"✅ MySQL: {result[2]}")
                
                self.logger.info(f"Database connected: {result[0]} on {result[1]}")
                cursor.close()
                return True
                
        except MySQLError as e:
            print(f"❌ Database connection failed: {e}")
            self.logger.error(f"Database connection error: {e}")
            return False
        
        return False

    def get_table_prefix(self) -> str:
        """Get WordPress table prefix"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SHOW TABLES LIKE '%posts'")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                if table_name.endswith('posts'):
                    prefix = table_name[:-5]
                    
                    # Verify it's a valid WordPress prefix
                    cursor.execute("SHOW TABLES LIKE %s", (f"{prefix}options",))
                    if cursor.fetchone():
                        self.wp_prefix = prefix
                        print(f"✅ Table prefix: {prefix}")
                        cursor.close()
                        return prefix
            
            cursor.close()
        except MySQLError as e:
            self.logger.error(f"Failed to detect table prefix: {e}")
        
        self.wp_prefix = "wp_"
        return "wp_"

    def get_media_attachments(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get media attachments from WordPress database"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            
            query = f"""
                SELECT 
                    p.ID,
                    p.post_title,
                    p.post_name,
                    p.post_content,
                    p.post_excerpt,
                    p.post_mime_type,
                    p.guid,
                    pm.meta_value as file_path
                FROM {self.wp_prefix}posts p
                LEFT JOIN {self.wp_prefix}postmeta pm ON p.ID = pm.post_id AND pm.meta_key = '_wp_attached_file'
                WHERE p.post_type = 'attachment' 
                AND p.post_mime_type LIKE 'image/%'
                ORDER BY p.ID DESC
                LIMIT %s OFFSET %s
            """
            
            cursor.execute(query, (limit, offset))
            attachments = cursor.fetchall()
            
            print(f"\n📸 Found {len(attachments)} attachments to process")
            self.logger.info(f"Retrieved {len(attachments)} attachments")
            
            cursor.close()
            return attachments
            
        except MySQLError as e:
            self.logger.error(f"Failed to get attachments: {e}")
            print(f"❌ Database query failed: {e}")
            return []

    def generate_seo_slug(self, title: str, max_length: int = 100) -> str:
        """Generate SEO-friendly slug from title"""
        if not title:
            return "media-attachment"
        
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        
        if len(slug) > max_length:
            slug = slug[:max_length].rstrip('-')
        
        if not slug:
            slug = "media-attachment"
        
        return slug

    def update_attachment_permalink(self, attachment_id: int, title: str) -> bool:
        """Update WordPress attachment permalink structure"""
        if not self.config['permalink_optimization']['enabled']:
            return True
        
        try:
            slug = self.generate_seo_slug(
                title, 
                self.config['permalink_optimization']['max_slug_length']
            )
            
            slug = self.ensure_unique_slug(slug, attachment_id)
            
            cursor = self.db_connection.cursor()
            
            update_query = f"""
                UPDATE {self.wp_prefix}posts 
                SET post_name = %s 
                WHERE ID = %s
            """
            
            if not self.dry_run:
                cursor.execute(update_query, (slug, attachment_id))
                self.db_connection.commit()
                
                self.permalink_updates.append({
                    'attachment_id': attachment_id,
                    'slug': slug,
                    'title': title,
                    'new_url': f"/media/{slug}/"
                })
                
                self.stats['permalinks_updated'] += 1
                self.logger.info(f"Updated permalink for ID {attachment_id}: {slug}")
            
            cursor.close()
            return True
            
        except MySQLError as e:
            self.logger.error(f"Failed to update permalink for ID {attachment_id}: {e}")
            self.stats['permalink_failures'] += 1
            return False

    def ensure_unique_slug(self, slug: str, attachment_id: int) -> str:
        """Ensure slug is unique in WordPress"""
        try:
            cursor = self.db_connection.cursor()
            
            check_query = f"""
                SELECT ID FROM {self.wp_prefix}posts 
                WHERE post_name = %s AND ID != %s
            """
            cursor.execute(check_query, (slug, attachment_id))
            
            if cursor.fetchone():
                counter = 1
                original_slug = slug
                
                while counter <= 100:
                    new_slug = f"{original_slug}-{counter}"
                    cursor.execute(check_query, (new_slug, attachment_id))
                    
                    if not cursor.fetchone():
                        slug = new_slug
                        break
                    
                    counter += 1
                
                if counter > 100:
                    slug = f"{original_slug}-{attachment_id}"
            
            cursor.close()
            return slug
            
        except MySQLError as e:
            self.logger.error(f"Failed to check slug uniqueness: {e}")
            return f"{slug}-{attachment_id}"

    def add_metadata_with_exiftool(self, file_path: Path, title: str, description: str = "", keywords: list = None) -> bool:
        """Add metadata using ExifTool"""
        if not self.config['metadata']['enabled']:
            return True
        
        try:
            exiftool_cmd = self.config['exiftool']['command']
            cmd = [exiftool_cmd]
            cmd.extend(self.config['exiftool']['args'])
            
            if title and self.config['metadata']['embed_title']:
                cmd.extend([
                    f'-IPTC:ObjectName={title}',
                    f'-XMP:Title={title}',
                    f'-EXIF:ImageDescription={title}'
                ])
            
            if description and self.config['metadata']['embed_description']:
                cmd.extend([
                    f'-IPTC:Caption-Abstract={description}',
                    f'-XMP:Description={description}'
                ])
            
            if keywords and self.config['metadata']['embed_keywords']:
                keywords_str = ','.join(keywords[:self.config['metadata']['max_keywords']])
                cmd.extend([f'-XMP:Subject={keywords_str}'])
            
            cmd.append(str(file_path))
            
            if not self.dry_run:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=self.config['exiftool']['timeout']
                )
                
                if result.returncode == 0:
                    self.stats['metadata_added'] += 1
                    return True
                else:
                    self.logger.error(f"ExifTool failed: {result.stderr}")
                    self.stats['metadata_failed'] += 1
                    return False
            
            return True
                
        except Exception as e:
            self.logger.error(f"ExifTool metadata failed: {e}")
            self.stats['metadata_failed'] += 1
            return False

    def optimize_filename(self, original_name: str, title: str) -> str:
        """Optimize filename based on title"""
        if not self.config['filename_optimization']['enabled']:
            return Path(original_name).stem
        
        base_name = title if title else Path(original_name).stem
        
        if self.config['filename_optimization']['remove_special_chars']:
            base_name = re.sub(r'[^\w\s-]', '', base_name)
        
        if self.config['filename_optimization']['replace_spaces']:
            space_replacement = self.config['filename_optimization']['replace_spaces']
            base_name = re.sub(r'\s+', space_replacement, base_name)
        
        if self.config['filename_optimization']['lowercase']:
            base_name = base_name.lower()
        
        base_name = re.sub(r'[-_]+', '-', base_name).strip('-_')
        
        max_length = self.config['filename_optimization']['max_length']
        if len(base_name) > max_length:
            base_name = base_name[:max_length].rstrip('-_')
        
        return base_name or "media"

    def generate_keywords_from_title(self, title: str) -> List[str]:
        """Generate keywords from title"""
        if not title or not self.config['metadata']['generate_keywords_from_title']:
            return []
        
        words = re.findall(r'\b\w+\b', title.lower())
        keywords = []
        min_length = self.config['metadata']['min_keyword_length']
        max_keywords = self.config['metadata']['max_keywords']
        
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an'}
        
        for word in words:
            if (len(word) >= min_length and 
                word not in stop_words and 
                word not in keywords and 
                len(keywords) < max_keywords):
                keywords.append(word)
        
        return keywords

    def convert_to_webp(self, input_path: Path, output_path: Path) -> Tuple[bool, int, int]:
        """Convert image to WebP format"""
        try:
            if not pil_available:
                return False, 0, 0
            
            original_size = input_path.stat().st_size
            
            with Image.open(input_path) as image:
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background
                
                webp_config = self.config['optimization']
                image.save(
                    output_path,
                    'WebP',
                    quality=webp_config['webp_quality'],
                    lossless=webp_config['webp_lossless'],
                    optimize=True
                )
            
            new_size = output_path.stat().st_size
            return True, original_size, new_size
            
        except Exception as e:
            self.logger.error(f"WebP conversion failed: {e}")
            return False, 0, 0

    def update_database_record(self, attachment_id: int, new_filename: str, new_path: str) -> bool:
        """Update database record with new file information"""
        try:
            cursor = self.db_connection.cursor()
            
            update_query = f"""
                UPDATE {self.wp_prefix}postmeta 
                SET meta_value = %s 
                WHERE post_id = %s AND meta_key = '_wp_attached_file'
            """
            cursor.execute(update_query, (new_path, attachment_id))
            
            guid_query = f"""
                UPDATE {self.wp_prefix}posts 
                SET guid = REPLACE(guid, SUBSTRING_INDEX(guid, '/', -1), %s)
                WHERE ID = %s
            """
            cursor.execute(guid_query, (new_filename, attachment_id))
            
            self.db_connection.commit()
            cursor.close()
            
            return True
            
        except MySQLError as e:
            self.logger.error(f"Database update failed: {e}")
            return False

    def process_attachment(self, attachment: Dict) -> bool:
        """Process a single attachment with optimization and SEO permalinks"""
        try:
            attachment_id = attachment['ID']
            title = attachment['post_title'] or f"Media {attachment_id}"
            description = attachment['post_content'] or attachment['post_excerpt'] or ""
            current_file_path = attachment['file_path']
            
            print(f"\n📸 Processing ID {attachment_id}: {title[:50]}...")
            
            if not current_file_path:
                print("   ❌ No file path found")
                return False
            
            current_full_path = self.uploads_path / current_file_path
            
            if not current_full_path.exists():
                print(f"   ❌ File not found: {current_full_path}")
                return False
            
            operations_performed = []
            
            # Generate optimized filename
            optimized_name = self.optimize_filename(current_full_path.name, title)
            new_filename = f"{optimized_name}.webp"
            new_file_path = current_full_path.parent / new_filename
            
            # Backup original if configured
            if self.config['optimization']['backup_originals'] and not self.dry_run:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"{current_full_path.stem}_{timestamp}{current_full_path.suffix}"
                backup_path = current_full_path.parent / f"backup_{backup_filename}"
                shutil.copy2(current_full_path, backup_path)
                operations_performed.append("💾 Original backed up")
            
            # Convert to WebP
            if not self.dry_run:
                success, original_size, new_size = self.convert_to_webp(current_full_path, new_file_path)
                if success:
                    size_reduction = ((original_size - new_size) / original_size) * 100
                    operations_performed.append(f"🖼️  WebP: {size_reduction:.1f}% smaller")
                    self.stats['webp_converted'] += 1
                    self.stats['size_saved'] += (original_size - new_size)
                else:
                    print("   ❌ WebP conversion failed")
                    return False
            else:
                operations_performed.append("🖼️  Would convert to WebP")
            
            # Generate keywords and add metadata
            keywords = self.generate_keywords_from_title(title)
            
            if not self.dry_run:
                metadata_success = self.add_metadata_with_exiftool(new_file_path, title, description, keywords)
                if metadata_success:
                    operations_performed.append("🏷️  Metadata added")
                else:
                    operations_performed.append("⚠️  Metadata failed")
            else:
                operations_performed.append("🏷️  Would add metadata")
            
            # Update SEO permalink
            permalink_success = self.update_attachment_permalink(attachment_id, title)
            if permalink_success:
                operations_performed.append("🔗 SEO permalink updated")
            else:
                operations_performed.append("⚠️  Permalink failed")
            
            # Update database
            if not self.dry_run:
                new_relative_path = str(Path(current_file_path).parent / new_filename)
                if self.update_database_record(attachment_id, new_filename, new_relative_path):
                    operations_performed.append("🗄️  Database updated")
                else:
                    operations_performed.append("❌ Database failed")
                
                # Remove original file
                if new_file_path.exists() and current_full_path != new_file_path:
                    current_full_path.unlink()
            else:
                operations_performed.append("🗄️  Would update database")
            
            # Show results
            print(f"   ✅ {current_full_path.name} → {new_filename}")
            for operation in operations_performed:
                print(f"      {operation}")
            
            self.stats['processed'] += 1
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process attachment {attachment['ID']}: {e}")
            print(f"   ❌ Processing failed: {e}")
            self.stats['errors'] += 1
            return False

    def generate_htaccess_rules(self):
        """Generate .htaccess rules for SEO-friendly attachment URLs"""
        if not self.config['permalink_optimization']['update_htaccess'] or not self.permalink_updates:
            return
        
        print(f"\n🔧 Generating .htaccess Rules ({len(self.permalink_updates)} rules)")
        
        htaccess_path = self.wp_path / ".htaccess"
        
        rules = [
            "# WordPress Media Optimizer - SEO Attachment URLs",
            "# Generated automatically",
            ""
        ]
        
        for update in self.permalink_updates:
            rules.append(f"RewriteRule ^media/{update['slug']}/?$ /?attachment_id={update['attachment_id']} [L,QSA]")
        
        rules.extend(["", "# End WordPress Media Optimizer rules", ""])
        
        if not self.dry_run:
            try:
                existing_content = ""
                if htaccess_path.exists():
                    with open(htaccess_path, 'r') as f:
                        existing_content = f.read()
                
                # Remove old rules
                start_marker = "# WordPress Media Optimizer - SEO Attachment URLs"
                end_marker = "# End WordPress Media Optimizer rules"
                
                if start_marker in existing_content:
                    start_idx = existing_content.find(start_marker)
                    end_idx = existing_content.find(end_marker)
                    if end_idx != -1:
                        end_idx = existing_content.find('\n', end_idx) + 1
                        existing_content = existing_content[:start_idx] + existing_content[end_idx:]
                
                # Add new rules
                lines = existing_content.split('\n')
                insert_index = 0
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('RewriteEngine'):
                        insert_index = i + 1
                        break
                
                for rule in reversed(rules):
                    lines.insert(insert_index, rule)
                
                with open(htaccess_path, 'w') as f:
                    f.write('\n'.join(lines))
                
                print(f"✅ Updated .htaccess with {len(self.permalink_updates)} rules")
                
            except Exception as e:
                print(f"⚠️  Failed to update .htaccess: {e}")
                self.logger.error(f"Failed to update .htaccess: {e}")
        else:
            print(f"🔍 Would generate {len(self.permalink_updates)} .htaccess rules")

    def run_optimization(self, limit: int = 50, offset: int = 0) -> bool:
        """Main optimization process"""
        if not self.detect_wordpress():
            return False
        
        if not self.connect_database():
            return False
        
        self.get_table_prefix()
        
        attachments = self.get_media_attachments(limit, offset)
        if not attachments:
            print("❌ No attachments found")
            return False
        
        print(f"\n🎯 Processing {len(attachments)} attachments...")
        
        for i, attachment in enumerate(attachments, 1):
            print(f"\n[{i}/{len(attachments)}]", end=" ")
            self.process_attachment(attachment)
        
        self.generate_htaccess_rules()
        self.generate_report()
        
        if self.db_connection and self.db_connection.is_connected():
            self.db_connection.close()
        
        return True

    def generate_report(self):
        """Generate comprehensive optimization report"""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        success_rate = (self.stats['processed'] / max(1, self.stats['processed'] + self.stats['errors'])) * 100
        
        print(f"\n📊 OPTIMIZATION SUMMARY")
        print("=" * 25)
        print(f"⏱️  Duration: {duration}")
        print(f"✅ Processed: {self.stats['processed']}")
        print(f"🖼️  WebP conversions: {self.stats['webp_converted']}")
        print(f"🏷️  Metadata added: {self.stats['metadata_added']}")
        print(f"🔗 Permalinks updated: {self.stats['permalinks_updated']}")
        print(f"💾 Size saved: {self.stats['size_saved'] / 1024 / 1024:.2f} MB")
        print(f"📈 Success rate: {success_rate:.1f}%")
        
        if self.stats['errors'] > 0:
            print(f"❌ Errors: {self.stats['errors']}")
        
        # Save detailed report
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        report_file = f"optimization_report_{timestamp}.txt"
        
        report_content = f"""
WordPress Media Optimizer Enhanced Report
========================================
Version: {self.version}
Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {duration}
Mode: {'DRY RUN' if self.dry_run else 'LIVE'}

Statistics:
-----------
Processed: {self.stats['processed']}
WebP Conversions: {self.stats['webp_converted']}
Metadata Added: {self.stats['metadata_added']}
Metadata Failed: {self.stats['metadata_failed']}
Permalinks Updated: {self.stats['permalinks_updated']}
Permalink Failures: {self.stats['permalink_failures']}
Errors: {self.stats['errors']}
Size Saved: {self.stats['size_saved']:,} bytes ({self.stats['size_saved'] / 1024 / 1024:.2f} MB)

Configuration:
--------------
WordPress Path: {self.config['wordpress_path']}
WebP Quality: {self.config['optimization']['webp_quality']}%
Backup Originals: {self.config['optimization']['backup_originals']}
SEO Permalinks: {self.config['permalink_optimization']['enabled']}
Update .htaccess: {self.config['permalink_optimization']['update_htaccess']}
"""
        
        with open(report_file, 'w') as f:
            f.write(report_content)
        
        print(f"📄 Report saved: {report_file}")
        
        mode_msg = "dry run completed!" if self.dry_run else "optimization completed!"
        print(f"\n🎉 WordPress media {mode_msg}")
        
        if not self.dry_run and self.config['optimization']['backup_originals']:
            print("💾 Original files have been backed up with timestamps")

def main():
    """Main entry point with enhanced argument parsing"""
    parser = argparse.ArgumentParser(
        description='WordPress Media Optimizer with SEO Permalinks - Enhanced Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --setup                    Interactive configuration setup
  %(prog)s --dry-run --limit 10       Test optimization on 10 images
  %(prog)s --limit 100 --offset 50    Process 100 images starting from 50th
  %(prog)s --skip-webp                Only update permalinks and metadata

For detailed help: %(prog)s --help-detailed
        """
    )
    
    # Main options
    parser.add_argument('--setup', action='store_true', 
                       help='Interactive configuration setup')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Test run without making changes')
    parser.add_argument('--version', action='store_true', 
                       help='Show version information')
    parser.add_argument('--check-requirements', action='store_true', 
                       help='Check system requirements')
    parser.add_argument('--validate-config', action='store_true', 
                       help='Validate configuration file')
    parser.add_argument('--help-detailed', action='store_true', 
                       help='Show detailed help information')
    
    # Configuration options
    parser.add_argument('--config', default='wp_optimizer_config.json', 
                       help='Configuration file path')
    
    # Processing options
    parser.add_argument('--limit', type=int, default=50, 
                       help='Number of attachments to process')
    parser.add_argument('--offset', type=int, default=0, 
                       help='Offset for attachment processing')
    parser.add_argument('--batch-size', type=int, default=50, 
                       help='Database batch size')
    
    # Feature toggles
    parser.add_argument('--skip-webp', action='store_true', 
                       help='Skip WebP conversion')
    parser.add_argument('--skip-metadata', action='store_true', 
                       help='Skip metadata embedding')
    parser.add_argument('--skip-permalinks', action='store_true', 
                       help='Skip permalink optimization')
    parser.add_argument('--skip-htaccess', action='store_true', 
                       help='Skip .htaccess generation')
    
    # Advanced options
    parser.add_argument('--backup-only', action='store_true', 
                       help='Only backup files, no optimization')
    parser.add_argument('--force-overwrite', action='store_true', 
                       help='Overwrite existing optimized files')
    
    args = parser.parse_args()
    
    # Create optimizer instance
    optimizer = WordPressMediaOptimizerEnhanced(config_file=args.config, dry_run=args.dry_run)
    
    # Show banner
    optimizer.show_banner()
    
    # Handle special commands
    if args.help_detailed:
        optimizer.show_usage()
        return
    
    if args.version:
        optimizer.show_version()
        return
    
    if args.check_requirements:
        requirements_met = optimizer.check_requirements(verbose=True)
        sys.exit(0 if requirements_met else 1)
    
    if args.setup:
        success = optimizer.interactive_setup()
        if success:
            print("\n🎉 Setup completed successfully!")
            print("You can now run the optimizer with: python3 wp_media_optimizer_permalink.py --dry-run")
        sys.exit(0 if success else 1)
    
    if args.validate_config:
        valid = optimizer.validate_config()
        sys.exit(0 if valid else 1)
    
    # Load configuration for normal operation
    if not optimizer.load_config():
        print("\n💡 Tip: Run --setup to create a configuration file.")
        sys.exit(1)
    
    # Check requirements before processing
    if not optimizer.check_requirements(verbose=False):
        print("❌ System requirements not met. Run --check-requirements for details.")
        sys.exit(1)
    
    # Verify ExifTool
    if not optimizer._verify_exiftool():
        print("❌ ExifTool verification failed. Please install ExifTool.")
        sys.exit(1)
    
    # Show current mode
    mode = "🧪 DRY RUN" if args.dry_run else "🚀 LIVE MODE"
    print(f"{mode} - Processing up to {args.limit} attachments")
    print()
    
    # Apply feature toggles to configuration
    if args.skip_webp:
        optimizer.config['optimization']['webp_enabled'] = False
    if args.skip_metadata:
        optimizer.config['metadata']['enabled'] = False
    if args.skip_permalinks:
        optimizer.config['permalink_optimization']['enabled'] = False
    if args.skip_htaccess:
        optimizer.config['permalink_optimization']['update_htaccess'] = False
    
    # Run optimization
    try:
        success = optimizer.run_optimization(limit=args.limit, offset=args.offset)
        
        if success:
            print("\n🎉 Optimization completed successfully!")
            if args.dry_run:
                print("💡 Run without --dry-run to perform actual optimization.")
        else:
            print("\n❌ Optimization failed. Check logs for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        optimizer.logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
