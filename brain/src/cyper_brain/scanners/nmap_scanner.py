"""
Nmap Scanner Integration

Implements actual network scanning using python-nmap library.
Follows TDD principles - tests written first in test_nmap_scanner.py
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from xml.etree import ElementTree as ET

import nmap

logger = logging.getLogger(__name__)


@dataclass
class Service:
    """Represents a discovered service on a port"""
    port: int
    name: str
    product: Optional[str] = None
    version: Optional[str] = None
    extra_info: Optional[str] = None
    state: str = "open"
    
    def to_dict(self) -> Dict:
        return {
            "port": self.port,
            "name": self.name,
            "product": self.product,
            "version": self.version,
            "extra_info": self.extra_info,
            "state": self.state
        }


@dataclass
class ScanResult:
    """Represents the results of an Nmap scan"""
    target: str
    open_ports: List[int] = field(default_factory=list)
    services: List[Service] = field(default_factory=list)
    os_matches: List[Dict] = field(default_factory=list)
    scan_time: float = 0.0
    
    def is_port_open(self, port: int) -> bool:
        """Check if a specific port is open"""
        return port in self.open_ports
    
    def get_service(self, port: int) -> Optional[Service]:
        """Get service information for a specific port"""
        for service in self.services:
            if service.port == port:
                return service
        return None
    
    def get_services(self) -> List[Service]:
        """Get all discovered services"""
        return self.services
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for AI analysis"""
        return {
            "target": self.target,
            "open_ports": self.open_ports,
            "services": [s.to_dict() for s in self.services],
            "os_matches": self.os_matches,
            "scan_time": self.scan_time
        }


class NmapResultParser:
    """Parses Nmap XML output"""
    
    def parse_xml(self, xml_string: str) -> ScanResult:
        """Parse Nmap XML output into ScanResult"""
        root = ET.fromstring(xml_string)
        
        # Get target IP
        host = root.find('.//host')
        if host is None:
            raise ValueError("No host found in XML")
        
        address = host.find('address')
        target = address.get('addr') if address is not None else "unknown"
        
        # Parse ports
        open_ports = []
        services = []
        
        for port in host.findall('.//port'):
            port_id = int(port.get('portid'))
            state = port.find('state')
            
            if state is not None and state.get('state') == 'open':
                open_ports.append(port_id)
                
                # Parse service info
                service_elem = port.find('service')
                if service_elem is not None:
                    service = Service(
                        port=port_id,
                        name=service_elem.get('name', 'unknown'),
                        product=service_elem.get('product'),
                        version=service_elem.get('version'),
                        extra_info=service_elem.get('extrainfo')
                    )
                    services.append(service)
        
        return ScanResult(
            target=target,
            open_ports=open_ports,
            services=services
        )


class NmapScanner:
    """
    Nmap Scanner Wrapper
    
    Provides async and sync scanning capabilities with TDD design.
    """
    
    def __init__(self, timeout: int = 300):
        """
        Initialize scanner
        
        Args:
            timeout: Maximum scan time in seconds (default: 300 = 5 minutes)
        """
        self.timeout = timeout
        self.nm = nmap.PortScanner()
        self.parser = NmapResultParser()
    
    def _validate_target(self, target: str) -> None:
        """Validate target format"""
        # Basic validation - no spaces, basic domain/IP format
        if not target or ' ' in target:
            raise ValueError(f"Invalid target: {target}")
        
        # Check for obviously invalid formats
        if target.count('.') > 3 and ':' not in target:  # Not IPv6
            raise ValueError(f"Invalid target: {target}")
    
    def scan(
        self,
        target: str,
        ports: str = "1-1000",
        service_detection: bool = False,
        version_detection: bool = False,
        os_detection: bool = False
    ) -> ScanResult:
        """
        Perform synchronous port scan
        
        Args:
            target: IP address or hostname
            ports: Port range (e.g., "22,80,443" or "1-1000")
            service_detection: Enable service/version detection
            version_detection: Enable version detection (implies service_detection)
            os_detection: Enable OS detection (requires root)
        
        Returns:
            ScanResult object with scan findings
        
        Raises:
            ValueError: Invalid target
            TimeoutError: Scan exceeded timeout
        """
        self._validate_target(target)
        
        # Build scan arguments
        arguments = f"-p {ports}"
        
        if version_detection or service_detection:
            arguments += " -sV"  # Service/version detection
        
        if os_detection:
            arguments += " -O"  # OS detection
        
        # Add timeout
        arguments += f" --host-timeout {self.timeout}s"
        
        logger.info(f"Starting Nmap scan of {target} with args: {arguments}")
        
        try:
            # Execute scan
            self.nm.scan(hosts=target, arguments=arguments)
            
            # Parse results
            result = self._parse_results(target)
            
            logger.info(f"Scan complete: {len(result.open_ports)} open ports found")
            return result
            
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError(f"Scan of {target} exceeded {self.timeout}s timeout")
            raise
    
    async def scan_async(
        self,
        target: str,
        ports: str = "1-1000",
        **kwargs
    ) -> ScanResult:
        """
        Perform asynchronous port scan
        
        Args:
            target: IP address or hostname
            ports: Port range
            **kwargs: Additional arguments passed to scan()
        
        Returns:
            ScanResult object
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.scan(target, ports, **kwargs)
        )
    
    def _parse_results(self, target: str) -> ScanResult:
        """Parse Nmap results into ScanResult object"""
        open_ports = []
        services = []
        
        # Check if target was scanned
        if target not in self.nm.all_hosts():
            return ScanResult(target=target)
        
        # Parse port information
        for proto in self.nm[target].all_protocols():
            ports = self.nm[target][proto].keys()
            
            for port in ports:
                port_info = self.nm[target][proto][port]
                
                if port_info['state'] == 'open':
                    open_ports.append(port)
                    
                    # Extract service info
                    service = Service(
                        port=port,
                        name=port_info.get('name', 'unknown'),
                        product=port_info.get('product'),
                        version=port_info.get('version'),
                        extra_info=port_info.get('extrainfo'),
                        state=port_info['state']
                    )
                    services.append(service)
        
        # Parse OS detection if available
        os_matches = []
        if 'osmatch' in self.nm[target]:
            os_matches = [
                {
                    'name': match['name'],
                    'accuracy': match['accuracy']
                }
                for match in self.nm[target]['osmatch']
            ]
        
        return ScanResult(
            target=target,
            open_ports=sorted(open_ports),
            services=services,
            os_matches=os_matches,
            scan_time=self.nm.scanstats().get('elapsed', 0.0)
        )
