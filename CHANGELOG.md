# Changelog

## In Development
- Enhanced AI context generation to include multiple paragraphs (up to 2000 characters) instead of just adjacent paragraphs
  - Frontend now collects context from multiple preceding and following sections
  - Backend truncates context to 2000 characters (last 2000 for previous context, first 2000 for next context)
  - Provides richer context for AI text generation while managing token usage
  - Added comprehensive tests: truncation with long paragraphs and multi-paragraph collection with short paragraphs

## 0.1.1
- Addressed "information exposure through exception" issue
- Specified python 3.11.4 or higher to mitigate CVE-2025-8869 (pip symbolic link path traversal)
  - Python >=3.11.4 implements PEP 706 which provides safe tar extraction
  - Significantly reduces attack surface for this vulnerability
  - Full fix requires pip 25.3+ (not yet released)
- Migrated Docker base image from python:3.13-slim (Debian) to fedora:latest for improved security posture
  - Eliminates OpenSSH vulnerability (null character in ssh:// URI leading to code execution via ProxyCommand)
  - Eliminates Perl File::Temp insecure temporary file handling vulnerabilities
  - Reduces attack surface by using minimal Fedora base without unnecessary packages
  - Maintains consistency with TalkPipe project architecture

## 0.1.0
- Improved working version with multi-user accounts

## 0.0.1
- Basic working version using jupyter notebook-like tokens