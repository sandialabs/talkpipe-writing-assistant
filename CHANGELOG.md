# Changelog

## In Development
- Made AI generation mode buttons smaller and arranged in a single row for better visibility on small screens
- Fixed potential performance issue causing progressive slowdown during extended editing sessions
  - Removed 34 debug console.log statements that fired on every keystroke
  - Eliminated logging of full document text and section arrays during typing
  - Retained one-time initialization logs for startup troubleshooting
- Optimized section parsing performance for smoother typing experience
  - Added 150ms debounce to parseSections to avoid expensive operations on every keystroke
  - Added length pre-filter to skip Levenshtein distance calculation when strings differ by >2x in length
  - Implemented index-based matching to check same-position sections first before searching all sections
  - Fixed suggestion panel stability: suggestions no longer flicker during typing
  - Keyup handler now only triggers cursor updates for navigation keys (arrows, Home, End, etc.)
  - Mode buttons and "Use suggestion" button no longer steal focus from the editor

## 0.1.2
- Enhanced AI context generation to include multiple paragraphs (up to 2000 characters) instead of just adjacent paragraphs
  - Frontend now collects context from multiple preceding and following sections
  - Backend truncates context to 2000 characters (last 2000 for previous context, first 2000 for next context)
  - Provides richer context for AI text generation while managing token usage
  - Added comprehensive tests: truncation with long paragraphs and multi-paragraph collection with short paragraphs
- Redesigned AI generation UI for improved usability
  - Removed separate "Generate" button
  - Replaced radio buttons with large, descriptive icon buttons (Ideas 💡, Rewrite ✏️, Improve ✨, Proofread 🔍)
  - Each button includes hover tooltips explaining its purpose
  - Direct click triggers generation immediately
  - Visual feedback with pulsing indicator during generation
  - Streamlined workflow reduces clicks and improves discoverability
- Fixed dark mode styling issues
  - Replaced hard-coded light backgrounds with CSS variables that adapt to dark mode
  - Fixed loading indicators, dropdowns, form inputs, sections, and containers
  - Dark mode now has consistent dark theming throughout the application
  - Improved text contrast and border visibility in dark mode
  - Fixed light mode background to use proper light gradient (was incorrectly using dark colors)
  - Background now properly changes when toggling between light and dark modes
- Adjusted prompt generation to make it clear what text was context and what was the target paragraph 

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