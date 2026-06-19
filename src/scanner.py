"""Security scanner for downloaded videos.

Supports ClamAV (local) and VirusTotal (cloud) scanning engines.
Uses random probability to decide whether to scan each file
(airport-style random checks).
"""

import hashlib
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

QUARANTINE_DIR = "quarantine"


class ScanResult:
    """Result of a security scan."""

    CLEAN = "clean"
    THREAT = "threat"
    SKIPPED = "skipped"
    ERROR = "error"

    def __init__(self, status: str, details: Optional[str] = None) -> None:
        """Initialize scan result.

        Args:
            status: One of CLEAN, THREAT, SKIPPED, ERROR.
            details: Additional details about the scan.
        """
        self.status = status
        self.details = details

    def is_clean(self) -> bool:
        """Check if the file is clean."""
        return self.status == self.CLEAN

    def is_threat(self) -> bool:
        """Check if the file is a threat."""
        return self.status == self.THREAT


class SecurityScanner:
    """Scans downloaded files for security threats."""

    def __init__(
        self,
        enabled: bool = True,
        engine: str = "clamav",
        scan_probability: float = 0.1,
        output_dir: str = "./downloads",
    ) -> None:
        """Initialize the security scanner.

        Args:
            enabled: Whether scanning is enabled.
            engine: Scanning engine ('clamav' or 'virustotal').
            scan_probability: Probability of scanning each file (0.0-1.0).
            output_dir: Base output directory (for quarantine path).
        """
        self.enabled = enabled
        self.engine = engine
        self.scan_probability = scan_probability
        self.output_dir = output_dir
        self.quarantine_dir = os.path.join(output_dir, QUARANTINE_DIR)

    def should_scan(self) -> bool:
        """Decide whether to scan this file based on probability.

        Returns:
            True if the file should be scanned.
        """
        if not self.enabled:
            return False
        return random.random() < self.scan_probability

    def scan(self, filepath: str) -> ScanResult:
        """Scan a file using the configured engine.

        Args:
            filepath: Path to the file to scan.

        Returns:
            ScanResult with the scan outcome.
        """
        if not self.should_scan():
            logger.debug("Escaneo omitido (probabilidad %.0f%%)", self.scan_probability * 100)
            return ScanResult(ScanResult.SKIPPED, "No seleccionado para escaneo")

        logger.info("Escaneando fichero: %s (engine=%s)", filepath, self.engine)

        if self.engine == "virustotal":
            return self._scan_virustotal(filepath)
        else:
            return self._scan_clamav(filepath)

    def _scan_clamav(self, filepath: str) -> ScanResult:
        """Scan a file using ClamAV.

        Args:
            filepath: Path to the file to scan.

        Returns:
            ScanResult with the scan outcome.
        """
        clamscan = shutil.which("clamscan")
        if clamscan is None:
            logger.warning(
                "ClamAV no está instalado. Instalalo con: sudo apt install clamav. "
                "Se omite el escaneo."
            )
            return ScanResult(ScanResult.SKIPPED, "ClamAV no disponible")

        try:
            result = subprocess.run(
                [clamscan, "--no-summary", filepath],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.info("ClamAV: fichero limpio")
                return ScanResult(ScanResult.CLEAN, "ClamAV: limpio")
            elif result.returncode == 1:
                threat_info = result.stdout.strip() or result.stderr.strip()
                logger.error("ClamAV: AMENAZA detectada - %s", threat_info)
                self._quarantine_file(filepath)
                return ScanResult(ScanResult.THREAT, f"ClamAV: {threat_info}")
            else:
                logger.warning("ClamAV: error inesperado (code=%d)", result.returncode)
                return ScanResult(ScanResult.ERROR, f"ClamAV error: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error("ClamAV: timeout escaneando %s", filepath)
            return ScanResult(ScanResult.ERROR, "ClamAV timeout")
        except Exception as e:
            logger.error("ClamAV: error escaneando %s: %s", filepath, e)
            return ScanResult(ScanResult.ERROR, str(e))

    def _scan_virustotal(self, filepath: str) -> ScanResult:
        """Scan a file using VirusTotal API.

        First checks by hash, then uploads if no previous result exists.

        Args:
            filepath: Path to the file to scan.

        Returns:
            ScanResult with the scan outcome.
        """
        load_dotenv()
        api_key = os.getenv("VT_API_KEY")
        if not api_key:
            logger.warning(
                "VT_API_KEY no definida. Configúrala en .env para usar VirusTotal. "
                "Se omite el escaneo."
            )
            return ScanResult(ScanResult.SKIPPED, "VT_API_KEY no disponible")

        try:
            file_hash = self._compute_sha256(filepath)
            logger.debug("SHA256: %s", file_hash)

            report = self._check_hash_virustotal(file_hash, api_key)
            if report is not None:
                return self._parse_vt_report(report)

            logger.info("Sin resultado previo en VirusTotal. Subiendo fichero...")
            return self._upload_and_scan_virustotal(filepath, api_key)

        except Exception as e:
            logger.error("VirusTotal: error escaneando %s: %s", filepath, e)
            return ScanResult(ScanResult.ERROR, str(e))

    def _compute_sha256(self, filepath: str) -> str:
        """Compute SHA256 hash of a file.

        Args:
            filepath: Path to the file.

        Returns:
            Hex digest of the SHA256 hash.
        """
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _check_hash_virustotal(
        self, file_hash: str, api_key: str
    ) -> Optional[dict]:
        """Check if a file hash has a previous VirusTotal report.

        Args:
            file_hash: SHA256 hash of the file.
            api_key: VirusTotal API key.

        Returns:
            Report data if found, None otherwise.
        """
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        headers = {"x-apikey": api_key}

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            logger.warning("VirusTotal API error (status=%d)", response.status_code)
            return None

    def _upload_and_scan_virustotal(
        self, filepath: str, api_key: str
    ) -> ScanResult:
        """Upload a file to VirusTotal and wait for scan results.

        Args:
            filepath: Path to the file to upload.
            api_key: VirusTotal API key.

        Returns:
            ScanResult with the scan outcome.
        """
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": api_key}

        file_size = os.path.getsize(filepath)
        if file_size > 32 * 1024 * 1024:
            logger.warning(
                "Fichero demasiado grande para VirusTotal (%.1f MB > 32 MB). "
                "Se omite el escaneo.",
                file_size / (1024 * 1024),
            )
            return ScanResult(ScanResult.SKIPPED, "Fichero > 32MB")

        with open(filepath, "rb") as f:
            response = requests.post(
                url,
                headers=headers,
                files={"file": (os.path.basename(filepath), f)},
                timeout=120,
            )

        if response.status_code != 200:
            logger.error("VirusTotal upload error: %s", response.text)
            return ScanResult(ScanResult.ERROR, f"VT upload error: {response.status_code}")

        analysis_id = response.json()["data"]["id"]
        logger.info("Fichero subido. Analysis ID: %s", analysis_id)

        return self._poll_vt_analysis(analysis_id, api_key)

    def _poll_vt_analysis(
        self, analysis_id: str, api_key: str, max_wait: int = 120
    ) -> ScanResult:
        """Poll VirusTotal for analysis results.

        Args:
            analysis_id: The analysis ID from the upload.
            api_key: VirusTotal API key.
            max_wait: Maximum seconds to wait for results.

        Returns:
            ScanResult with the scan outcome.
        """
        import time

        url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
        headers = {"x-apikey": api_key}

        start = time.time()
        while time.time() - start < max_wait:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                logger.warning("VT poll error: %d", response.status_code)
                time.sleep(10)
                continue

            data = response.json()
            status = data["data"]["attributes"]["status"]

            if status == "completed":
                return self._parse_vt_report(data)
            elif status == "error":
                return ScanResult(ScanResult.ERROR, "VT analysis error")

            logger.debug("VT analysis status: %s", status)
            time.sleep(10)

        return ScanResult(ScanResult.ERROR, "VT analysis timeout")

    def _parse_vt_report(self, report: dict) -> ScanResult:
        """Parse a VirusTotal report into a ScanResult.

        Args:
            report: The VirusTotal API response data.

        Returns:
            ScanResult with the scan outcome.
        """
        try:
            stats = report["data"]["attributes"]["stats"]
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)

            if malicious > 0:
                details = f"VT: {malicious} motores detectaron amenaza"
                logger.error("VirusTotal: AMENAZA - %s", details)
                return ScanResult(ScanResult.THREAT, details)
            elif suspicious > 0:
                details = f"VT: {suspicious} motores marcaron como sospechoso"
                logger.warning("VirusTotal: SOSPECHOSO - %s", details)
                return ScanResult(ScanResult.THREAT, details)
            else:
                logger.info("VirusTotal: fichero limpio")
                return ScanResult(ScanResult.CLEAN, "VirusTotal: limpio")
        except (KeyError, TypeError) as e:
            return ScanResult(ScanResult.ERROR, f"VT parse error: {e}")

    def _quarantine_file(self, filepath: str) -> None:
        """Move a threatening file to the quarantine directory.

        Args:
            filepath: Path to the file to quarantine.
        """
        os.makedirs(self.quarantine_dir, exist_ok=True)
        filename = os.path.basename(filepath)
        quarantine_path = os.path.join(self.quarantine_dir, filename)

        counter = 1
        while os.path.exists(quarantine_path):
            name, ext = os.path.splitext(filename)
            quarantine_path = os.path.join(
                self.quarantine_dir, f"{name}_quarantine_{counter}{ext}"
            )
            counter += 1

        shutil.move(filepath, quarantine_path)
        logger.critical(
            "Fichero movido a cuarentena: %s", quarantine_path
        )
