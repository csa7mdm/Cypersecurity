"""
SQLMap Scanner Integration

Automated SQL injection detection and exploitation.
Following TDD - tests in test_sqlmap_scanner.py
"""

import os
import logging
import subprocess
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class InjectionType(Enum):
    """SQL injection technique types"""
    BOOLEAN_BLIND = "boolean-based blind"
    TIME_BLIND = "time-based blind"
    ERROR_BASED = "error-based"
    UNION_QUERY = "UNION query"
    STACKED_QUERIES = "stacked queries"
    INLINE_QUERY = "inline query"


@dataclass
class InjectionPoint:
    """Represents a SQL injection vulnerability"""
    parameter: str
    parameter_type: str = "GET"  # GET, POST, COOKIE, HEADER
    injection_type: Optional[InjectionType] = None
    payload: str = ""
    vulnerable: bool = False
    dbms: Optional[str] = None
    title: str = ""
    
    def is_blind_injection(self) -> bool:
        """Check if this is a blind injection"""
        return self.injection_type in [
            InjectionType.BOOLEAN_BLIND,
            InjectionType.TIME_BLIND
        ]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "parameter": self.parameter,
            "parameter_type": self.parameter_type,
            "injection_type": self.injection_type.value if self.injection_type else None,
            "payload": self.payload,
            "vulnerable": self.vulnerable,
            "dbms": self.dbms,
            "title": self.title
        }


@dataclass
class SQLMapResult:
    """Results from SQLMap scan"""
    target_url: str
    injection_points: List[InjectionPoint] = field(default_factory=list)
    database_type: Optional[str] = None
    database_version: Optional[str] = None
    web_server: Optional[str] = None
    is_vulnerable: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for AI analysis"""
        return {
            "target_url": self.target_url,
            "is_vulnerable": self.is_vulnerable,
            "injection_points": [ip.to_dict() for ip in self.injection_points],
            "database_type": self.database_type,
            "database_version": self.database_version,
            "web_server": self.web_server
        }


class SQLMapScanner:
    """
    SQLMap SQL Injection Scanner
    
    Automated SQL injection detection and exploitation.
    Requires sqlmap to be installed (pip install sqlmap-python or system sqlmap)
    """
    
    def __init__(
        self,
        sqlmap_path: Optional[str] = None,
        timeout: int = 300
    ):
        """
        Initialize SQLMap scanner
        
        Args:
            sqlmap_path: Path to sqlmap.py (auto-detected if None)
            timeout: Maximum scan time in seconds
        """
        self.timeout = timeout
        
        # Try to find sqlmap
        if sqlmap_path:
            self.sqlmap_path = sqlmap_path
        else:
            # Common locations
            possible_paths = [
                "sqlmap",  # System PATH
                "/usr/local/bin/sqlmap",
                "/usr/bin/sqlmap",
                os.path.expanduser("~/.local/bin/sqlmap")
            ]
            
            self.sqlmap_path = "sqlmap"  # Default to PATH
            for path in possible_paths:
                if os.path.exists(path):
                    self.sqlmap_path = path
                    break
    
    def scan(
        self,
        url: str,
        method: str = "GET",
        data: Optional[str] = None,
        cookies: Optional[str] = None,
        risk_level: int = 1,
        techniques: str = "BEUST"
    ) -> SQLMapResult:
        """
        Scan URL for SQL injection vulnerabilities
        
        Args:
            url: Target URL
            method: HTTP method (GET/POST)
            data: POST data
            cookies: Cookie header
            risk_level: Risk level (1-3, higher = more tests)
            techniques: SQLMap techniques (B=Boolean, E=Error, U=Union, S=Stacked, T=Time)
        
        Returns:
            SQLMapResult with findings
        """
        logger.info(f"Starting SQLMap scan of {url}")
        
        # Build SQLMap command
        cmd = [
            self.sqlmap_path,
            "-u", url,
            "--batch",  # Never ask for user input
            "--random-agent",  # Use random User-Agent
            f"--risk={risk_level}",
            f"--technique={techniques}",
            f"--timeout={self.timeout}",
            "--threads=4",
            "--output-dir=/tmp/sqlmap"
        ]
        
        if method.upper() == "POST" and data:
            cmd.extend(["--method=POST", "--data", data])
        
        if cookies:
            cmd.extend(["--cookie", cookies])
        
        try:
            # Run SQLMap
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            output = result.stdout + result.stderr
            
            # Parse results
            scan_result = self._parse_results(url, output)
            
            logger.info(f"Scan complete: {len(scan_result.injection_points)} injection points found")
            return scan_result
            
        except subprocess.TimeoutExpired:
            logger.warning(f"SQLMap scan timeout after {self.timeout}s")
            return SQLMapResult(target_url=url)
        except FileNotFoundError:
            logger.error("SQLMap not found - please install: pip install sqlmap-python")
            raise
        except Exception as e:
            logger.error(f"SQLMap scan failed: {e}")
            raise
    
    def enumerate_databases(self, url: str) -> List[str]:
        """Enumerate available databases"""
        cmd = [
            self.sqlmap_path,
            "-u", url,
            "--batch",
            "--dbs"  # Enumerate databases
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            output = result.stdout
            
            # Parse database names
            databases = []
            in_db_section = False
            
            for line in output.split('\n'):
                if 'available databases' in line.lower():
                    in_db_section = True
                    continue
                
                if in_db_section and line.strip().startswith('[*]'):
                    db_name = line.strip()[3:].strip()
                    databases.append(db_name)
            
            return databases
            
        except Exception as e:
            logger.error(f"Database enumeration failed: {e}")
            return []
    
    def enumerate_tables(self, url: str, database: str) -> List[str]:
        """Enumerate tables in database"""
        cmd = [
            self.sqlmap_path,
            "-u", url,
            "--batch",
            "-D", database,
            "--tables"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            # Parse table names from output
            return self._parse_tables(result.stdout)
        except Exception as e:
            logger.error(f"Table enumeration failed: {e}")
            return []
    
    def _parse_results(self, url: str, output: str) -> SQLMapResult:
        """Parse SQLMap output"""
        result = SQLMapResult(target_url=url)
        
        # Check if vulnerable
        result.is_vulnerable = "appears to be injectable" in output.lower()
        
        # Parse injection points
        result.injection_points = self._parse_injections(output)
        
        # Parse database info
        db_info = self._parse_database_info(output)
        result.database_type = db_info.get("database_type")
        result.database_version = db_info.get("database_version")
        result.web_server = db_info.get("web_server")
        
        return result
    
    def _parse_injections(self, output: str) -> List[InjectionPoint]:
        """Parse injection points from output"""
        injections = []
        
        # Pattern to match injection details
        param_pattern = r"Parameter:\s+(\w+)\s+\((\w+)\)"
        type_pattern = r"Type:\s+(.+)"
        title_pattern = r"Title:\s+(.+)"
        payload_pattern = r"Payload:\s+(.+)"
        
        sections = output.split("---")
        
        for section in sections:
            if "Parameter:" not in section:
                continue
            
            param_match = re.search(param_pattern, section)
            type_match = re.search(type_pattern, section)
            title_match = re.search(title_pattern, section)
            payload_match = re.search(payload_pattern, section)
            
            if param_match:
                parameter = param_match.group(1)
                param_type = param_match.group(2)
                
                # Determine injection type
                injection_type = None
                if type_match:
                    type_str = type_match.group(1).strip()
                    if "boolean" in type_str.lower():
                        injection_type = InjectionType.BOOLEAN_BLIND
                    elif "time" in type_str.lower():
                        injection_type = InjectionType.TIME_BLIND
                    elif "error" in type_str.lower():
                        injection_type = InjectionType.ERROR_BASED
                    elif "union" in type_str.lower():
                        injection_type = InjectionType.UNION_QUERY
                    elif "stacked" in type_str.lower():
                        injection_type = InjectionType.STACKED_QUERIES
                
                injection = InjectionPoint(
                    parameter=parameter,
                    parameter_type=param_type,
                    injection_type=injection_type,
                    payload=payload_match.group(1).strip() if payload_match else "",
                    title=title_match.group(1).strip() if title_match else "",
                    vulnerable=True
                )
                
                injections.append(injection)
        
        return injections
    
    def _parse_database_info(self, output: str) -> Dict:
        """Parse database type and version"""
        info = {}
        
        # Database type
        dbms_match = re.search(r"back-end DBMS:\s+(\w+)", output)
        if dbms_match:
            info["database_type"] = dbms_match.group(1)
        
        # Database version
        version_match = re.search(r"back-end DBMS:\s+\w+\s+([>=<\d.]+)", output)
        if version_match:
            info["database_version"] = version_match.group(1).strip()
        
        # Web server
        server_match = re.search(r"web application technology:\s+(.+)", output)
        if server_match:
            tech = server_match.group(1).strip()
            if "Apache" in tech:
                info["web_server"] = "Apache"
            elif "nginx" in tech:
                info["web_server"] = "nginx"
            elif "IIS" in tech:
                info["web_server"] = "IIS"
        
        return info
    
    def _parse_tables(self, output: str) -> List[str]:
        """Parse table names from output"""
        tables = []
        in_table_section = False
        
        for line in output.split('\n'):
            if 'Database:' in line:
                in_table_section = True
                continue
            
            if in_table_section and line.strip().startswith('|'):
                # Parse table name from ASCII table
                parts = [p.strip() for p in line.split('|')]
                if len(parts) > 1 and parts[1]:
                    tables.append(parts[1])
        
        return tables
