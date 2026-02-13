"""
Jenkins Client for fetching jobs and configurations.
"""

import requests
from typing import Dict, List, Optional
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET


class JenkinsClient:
    """Client for interacting with Jenkins API."""

    def __init__(self, jenkins_url: str, username: str = "admin", password: str = "admin"):
        """
        Initialize Jenkins client.

        Args:
            jenkins_url: Base URL of Jenkins server (e.g., http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins)
            username: Jenkins username
            password: Jenkins password or API token
        """
        self.jenkins_url = jenkins_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password)
        self.session = requests.Session()
        self.session.auth = self.auth

    def get_jobs(self) -> List[Dict]:
        """
        Get list of all Jenkins jobs.

        Returns:
            List of job dictionaries with name, url, and color (status)
        """
        try:
            url = f"{self.jenkins_url}/api/json?tree=jobs[name,url,color,buildable]"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            jobs = data.get('jobs', [])

            # Filter and format jobs
            formatted_jobs = []
            for job in jobs:
                formatted_jobs.append({
                    'name': job.get('name'),
                    'url': job.get('url'),
                    'status': self._parse_job_status(job.get('color', '')),
                    'buildable': job.get('buildable', True)
                })

            return formatted_jobs

        except Exception as e:
            raise Exception(f"Failed to fetch Jenkins jobs: {str(e)}")

    def get_job_config(self, job_name: str) -> str:
        """
        Get XML configuration for a specific job.

        Args:
            job_name: Name of the Jenkins job

        Returns:
            XML configuration as string
        """
        try:
            url = f"{self.jenkins_url}/job/{job_name}/config.xml"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            return response.text

        except Exception as e:
            raise Exception(f"Failed to fetch job config for '{job_name}': {str(e)}")

    def extract_pipeline_script(self, config_xml: str) -> Optional[str]:
        """
        Extract pipeline script from job configuration XML.

        Args:
            config_xml: Jenkins job configuration XML

        Returns:
            Pipeline script content or None
        """
        try:
            root = ET.fromstring(config_xml)

            # Look for pipeline script in different locations
            # For Pipeline jobs
            script_elem = root.find('.//script')
            if script_elem is not None and script_elem.text:
                return script_elem.text.strip()

            # For scripted pipeline definition
            definition = root.find('.//definition')
            if definition is not None:
                script_elem = definition.find('.//script')
                if script_elem is not None and script_elem.text:
                    return script_elem.text.strip()

            # For SCM-based pipeline
            script_path = root.find('.//scriptPath')
            if script_path is not None:
                return f"# Pipeline script is in SCM at: {script_path.text}"

            return None

        except Exception as e:
            raise Exception(f"Failed to extract pipeline script: {str(e)}")

    def get_job_details(self, job_name: str) -> Dict:
        """
        Get detailed information about a specific job.

        Args:
            job_name: Name of the Jenkins job

        Returns:
            Dictionary with job details including pipeline script
        """
        try:
            # Get job info
            url = f"{self.jenkins_url}/job/{job_name}/api/json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            job_info = response.json()

            # Get job configuration
            config_xml = self.get_job_config(job_name)

            # Extract pipeline script
            pipeline_script = self.extract_pipeline_script(config_xml)

            # Get last build info
            last_build = job_info.get('lastBuild')
            last_build_info = None
            if last_build:
                last_build_info = {
                    'number': last_build.get('number'),
                    'url': last_build.get('url'),
                    'result': job_info.get('color', 'unknown')
                }

            return {
                'name': job_info.get('name'),
                'description': job_info.get('description', ''),
                'url': job_info.get('url'),
                'buildable': job_info.get('buildable', True),
                'pipeline_script': pipeline_script,
                'config_xml': config_xml,
                'last_build': last_build_info,
                'builds': job_info.get('builds', [])[:5]  # Last 5 builds
            }

        except Exception as e:
            raise Exception(f"Failed to get job details for '{job_name}': {str(e)}")

    def test_connection(self) -> Dict:
        """
        Test connection to Jenkins server.

        Returns:
            Dictionary with connection status
        """
        try:
            url = f"{self.jenkins_url}/api/json"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()

            return {
                'connected': True,
                'jenkins_version': response.headers.get('X-Jenkins', 'Unknown'),
                'jobs_count': len(data.get('jobs', [])),
                'url': self.jenkins_url
            }

        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': self.jenkins_url
            }

    def create_job(self, job_name: str, config_xml: str) -> Dict:
        """
        Create a new Jenkins job.

        Args:
            job_name: Name for the new job
            config_xml: XML configuration for the job

        Returns:
            Dictionary with creation status
        """
        try:
            url = f"{self.jenkins_url}/createItem?name={job_name}"
            headers = {'Content-Type': 'application/xml'}
            response = self.session.post(url, data=config_xml, headers=headers, timeout=10)
            response.raise_for_status()

            return {
                'success': True,
                'job_name': job_name,
                'job_url': f"{self.jenkins_url}/job/{job_name}",
                'message': f"Job '{job_name}' created successfully"
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                return {
                    'success': False,
                    'error': f"Job '{job_name}' already exists or invalid configuration",
                    'status_code': 400
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {e.response.status_code}: {str(e)}",
                    'status_code': e.response.status_code
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to create job: {str(e)}"
            }

    def _parse_job_status(self, color: str) -> str:
        """
        Parse Jenkins job color to human-readable status.

        Args:
            color: Jenkins job color code

        Returns:
            Human-readable status
        """
        status_map = {
            'blue': 'success',
            'blue_anime': 'building',
            'red': 'failed',
            'red_anime': 'building (previous failed)',
            'yellow': 'unstable',
            'yellow_anime': 'building (unstable)',
            'aborted': 'aborted',
            'aborted_anime': 'building (aborted)',
            'disabled': 'disabled',
            'notbuilt': 'not built',
            'grey': 'pending'
        }

        return status_map.get(color, 'unknown')
