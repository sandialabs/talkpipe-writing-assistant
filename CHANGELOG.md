# Changelog

## In Progress
- Addressed "information exposure through exception" issue
- Specified python 3.11.4 or higher to address CVE-2025-8869
- Removed openssh-client from Docker images to fix OpenSSH vulnerability (null character in ssh:// URI leading to code execution via ProxyCommand)
- Removed Perl packages from Docker images to fix File::Temp insecure temporary file handling vulnerabilities

## 0.1.0
- Improved working version with multi-user accounts

## 0.0.1
- Basic working version using jupyter notebook-like tokens