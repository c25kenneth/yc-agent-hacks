"""Repository indexing utilities for Captain knowledge base."""

import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any
from git import Repo
import base64


def clone_repository(repo_url: str, target_dir: Path) -> None:
    """Clone a GitHub repository to a local directory."""
    Repo.clone_from(repo_url, target_dir)


def get_indexable_files(repo_dir: Path) -> List[Path]:
    """
    Get all files that should be indexed from the repository.

    Filters out:
    - .git directory
    - node_modules
    - venv, __pycache__
    - Binary files
    - Large files (>1MB)
    """
    ignore_dirs = {
        '.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build',
        '.next', '.nuxt', 'coverage', '.pytest_cache', '.mypy_cache'
    }

    ignore_files = {
        '.DS_Store', 'Thumbs.db', 'package-lock.json', 'yarn.lock',
        'pnpm-lock.yaml', '.gitignore'
    }

    # Supported extensions (from Captain docs)
    indexable_extensions = {
        # Documents
        '.pdf', '.docx', '.txt', '.md',
        # Spreadsheets
        '.xlsx', '.xls', '.csv', '.json',
        # Presentations
        '.pptx', '.ppt',
        # Images (with OCR)
        '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff',
        # Code
        '.py', '.ts', '.js', '.html', '.css', '.php', '.java',
        '.tsx', '.jsx', '.vue', '.svelte', '.go', '.rs', '.rb',
        '.c', '.cpp', '.h', '.hpp', '.sh', '.bash', '.yaml', '.yml',
        '.toml', '.xml', '.sql', '.graphql', '.proto'
    }

    files_to_index = []

    for root, dirs, files in os.walk(repo_dir):
        # Remove ignored directories from search
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file in ignore_files:
                continue

            file_path = Path(root) / file

            # Check extension
            if file_path.suffix.lower() not in indexable_extensions:
                continue

            # Check file size (skip >1MB)
            try:
                if file_path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue

            files_to_index.append(file_path)

    return files_to_index


def prepare_file_for_captain(file_path: Path, repo_root: Path) -> Dict[str, Any]:
    """
    Prepare a file for indexing into Captain.

    Returns dict with file info for indexing.
    """
    relative_path = file_path.relative_to(repo_root)

    return {
        'path': str(relative_path),
        'full_path': str(file_path),
        'name': file_path.name,
        'extension': file_path.suffix,
        'size': file_path.stat().st_size
    }


def read_key_files(repo_dir: Path) -> Dict[str, str]:
    """
    Read key files from the repository for initial analysis.

    Returns dict of {filename: content}
    """
    key_files = [
        'README.md', 'README.txt', 'README',
        'package.json', 'pyproject.toml', 'setup.py', 'requirements.txt',
        'Cargo.toml', 'go.mod', 'pom.xml', 'build.gradle',
        'tsconfig.json', '.eslintrc', 'next.config.js', 'vite.config.ts'
    ]

    contents = {}

    for filename in key_files:
        file_path = repo_dir / filename
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                contents[filename] = content[:5000]  # First 5000 chars
            except Exception:
                pass

    return contents


def analyze_repository_structure(repo_dir: Path) -> Dict[str, Any]:
    """
    Analyze the repository structure and return metadata.
    """
    structure = {
        'directories': [],
        'file_counts_by_type': {},
        'total_files': 0,
        'languages_detected': set()
    }

    ignore_dirs = {'.git', 'node_modules', 'venv', '__pycache__'}

    language_extensions = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.jsx': 'JavaScript',
        '.java': 'Java',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.html': 'HTML',
        '.css': 'CSS',
        '.vue': 'Vue',
        '.svelte': 'Svelte'
    }

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        rel_path = Path(root).relative_to(repo_dir)
        if str(rel_path) != '.':
            structure['directories'].append(str(rel_path))

        for file in files:
            structure['total_files'] += 1
            ext = Path(file).suffix.lower()
            structure['file_counts_by_type'][ext] = structure['file_counts_by_type'].get(ext, 0) + 1

            if ext in language_extensions:
                structure['languages_detected'].add(language_extensions[ext])

    structure['languages_detected'] = list(structure['languages_detected'])

    return structure
