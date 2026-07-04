# MOSES.fs
## Machine-Organized Semantic Entity System

MOSES.fs is an autonomous, fully offline AI agent that transforms chaotic local file systems into structured, semantic knowledge graphs.

Designed specifically for edge devices and budget hardware (running flawlessly on 8GB RAM laptops), MOSES.fs operates invisibly in the background. It reads, tags, deduplicates, and sorts your files using local language and vision models, ensuring 100% data privacy with zero cloud dependency.

# Features
**Semantic Routing**: Files are moved and grouped by context, not just file extensions. A PDF receipt goes to /Finance/2026/, while a picture of a whiteboard goes to /Projects/Brainstorming/.

**Memory-Multiplexed AI**: Runs localized, lightweight models (like Qwen2.5-1.5B and Moondream2) sequentially, preventing RAM overload on constrained systems.

**Natural Language Search**: Instead of searching for IMG_8492.jpg, search your local drive for "the photo of the solar panel layout from last Tuesday."

**Zero-Cloud Privacy**: No API keys, no internet connection required, and zero data egress.

**Autonomous Optimization**: The background "Janitor" daemon automatically deduplicates identical files, compresses untouched cold data, and converts heavy media to modern, lightweight formats.