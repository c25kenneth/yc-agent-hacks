"""Test script for repository initialization with real file analysis."""

import asyncio
import sys
from pathlib import Path
from repo_indexer import (
    clone_repository,
    get_indexable_files,
    read_key_files,
    analyze_repository_structure
)


async def test_repo_analysis():
    """Test the repo analysis flow without calling the API."""

    repo = "tylerbordeaux/northstar-demo"
    github_token = None  # Will use public access

    if github_token:
        repo_url = f"https://{github_token}@github.com/{repo}.git"
    else:
        repo_url = f"https://github.com/{repo}.git"

    print(f"Testing repository analysis for: {repo}")
    print(f"Clone URL: {repo_url}")
    print("-" * 60)

    try:
        # Create temp directory
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        repo_path = temp_dir / "repo"

        print(f"\n1. Cloning repository to {repo_path}...")
        clone_repository(repo_url, repo_path)
        print("   ✓ Repository cloned successfully")

        print(f"\n2. Reading key files...")
        key_files = read_key_files(repo_path)
        print(f"   ✓ Found {len(key_files)} key files:")
        for filename, content in key_files.items():
            print(f"     - {filename} ({len(content)} chars)")

        print(f"\n3. Analyzing repository structure...")
        structure = analyze_repository_structure(repo_path)
        print(f"   ✓ Analysis complete:")
        print(f"     - Total files: {structure['total_files']}")
        print(f"     - Languages: {', '.join(structure['languages_detected'])}")
        print(f"     - Directories: {len(structure['directories'])}")
        print(f"     - File types:")
        for ext, count in sorted(structure['file_counts_by_type'].items(), key=lambda x: -x[1])[:10]:
            print(f"       {ext}: {count}")

        print(f"\n4. Getting indexable files...")
        indexable = get_indexable_files(repo_path)
        print(f"   ✓ Found {len(indexable)} indexable files")

        print(f"\n5. Sample of actual file contents:")
        print("=" * 60)
        for filename, content in list(key_files.items())[:2]:
            print(f"\n--- {filename} ---")
            print(content[:500])  # First 500 chars
            if len(content) > 500:
                print(f"\n... ({len(content) - 500} more characters)")

        print("\n" + "=" * 60)
        print("✓ Test complete - real analysis works!")
        print("\nNow the AI will receive ACTUAL file contents instead of guessing.")

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_repo_analysis())
