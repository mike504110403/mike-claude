"""Write PDF body to Markdown; stdout contains metadata only (Python 3.9+)."""

import argparse
import importlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


def protect_images(directory):
    """Only touch the dedicated directory we created; never follow image symlinks."""
    if directory.is_symlink():
        raise ValueError("refusing symlink image directory")
    for current, dirs, files in os.walk(str(directory), followlinks=False):
        current_path = Path(current)
        if current_path.is_symlink():
            raise ValueError("refusing symlink image directory")
        os.chmod(str(current_path), 0o700)
        for name in dirs:
            if (current_path / name).is_symlink():
                raise ValueError("refusing symlink image directory")
        for name in files:
            image = current_path / name
            if not stat.S_ISREG(image.lstat().st_mode):
                raise ValueError("image output must be a regular file")
            os.chmod(str(image), 0o600)


def write_markdown(output, markdown, overwrite):
    """Publish a complete private file without truncating an existing destination."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("refusing symlink output")
    descriptor, temporary = tempfile.mkstemp(prefix=".pdf2md-", dir=str(output.parent))
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(markdown)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            # Replace the directory entry; do not open/follow the destination.
            os.replace(temporary, str(output))
        else:
            # Atomic no-clobber publication. A concurrently created destination wins.
            os.link(temporary, str(output))
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if os.path.exists(temporary):
            os.unlink(temporary)


def select_pages(expression, total):
    if not expression:
        return list(range(total))
    result = set()
    for token in expression.split(","):
        bounds = token.strip().split("-")
        if len(bounds) == 1:
            start = end = int(bounds[0])
        elif len(bounds) == 2:
            start, end = map(int, bounds)
        else:
            raise ValueError("invalid page expression")
        if start < 1 or end < start:
            raise ValueError("pages must be positive ascending ranges")
        result.update(range(start - 1, min(end, total)))
    if not result:
        raise ValueError("no selected pages are within the PDF")
    return sorted(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("-p", "--pages", help="1-based: 1-20 or 3,5,7")
    parser.add_argument("--images", type=Path, help="new dedicated local image directory; existing paths are refused")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true", help="stderr diagnostics may contain sensitive document information")
    parser.add_argument("--_worker-metadata", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    source = args.input.resolve()
    # Absolute path without resolving a destination symlink.
    output = Path(os.path.abspath(str(args.output)))
    if not source.is_file() or source == output:
        parser.error("input must exist and differ from output")
    if output.exists() and os.path.samefile(str(source), str(output)):
        parser.error("output aliases the input file")
    if output.exists() and not args.overwrite:
        parser.error("output exists; inspect it before using --overwrite")
    if output.is_symlink():
        parser.error("refusing symlink output")
    if args.images and os.path.lexists(str(args.images)):
        parser.error("images requires a new dedicated directory, not an existing path")
    args.input, args.output = source, output
    if args.images:
        args.images = Path(os.path.abspath(str(args.images)))

    if args._worker_metadata is None:
        return isolated_conversion(args)
    return convert_worker(args, source, output)


def isolated_conversion(args):
    """Keep all converter output isolated until child exit, including C buffers."""
    try:
        with tempfile.TemporaryDirectory(prefix="pdf2md-") as scratch:
            metadata = Path(scratch) / "metadata.json"
            staged_body = Path(scratch) / "body.md"
            command = [sys.executable, str(Path(__file__).resolve()),
                       str(args.input), "-o", str(staged_body),
                       "--_worker-metadata", str(metadata)]
            if args.pages:
                command.extend(["-p", args.pages])
            if args.images:
                command.extend(["--images", str(args.images)])
            # Captured pipes stay attached until process termination. Buffered
            # native writes at shutdown can never reach this parent's stdout.
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if args.verbose:
                for diagnostics in (result.stdout, result.stderr):
                    if diagnostics:
                        sys.stderr.write(diagnostics.decode("utf-8", errors="replace"))
            if result.returncode == 3:
                print("Missing local dependency: pymupdf4llm/pymupdf. No installation performed.", file=sys.stderr)
                return 1
            if result.returncode != 0:
                print("PDF conversion failed; no success metadata produced.", file=sys.stderr)
                return 1
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            markdown = staged_body.read_text(encoding="utf-8")
            payload["output"] = str(args.output)
            report = json.dumps(payload, ensure_ascii=False)
        # Metadata parsing, body reading, report preparation and scratch cleanup
        # all finish before publication. Recheck the real target after the child.
        if args.output.is_symlink():
            raise ValueError("refusing symlink output")
        if args.output.exists():
            if os.path.samefile(str(args.input), str(args.output)):
                raise ValueError("output aliases the input file")
            if not args.overwrite:
                raise FileExistsError("output exists")
        # This helper stages in the destination directory, so the atomic publish
        # never depends on scratch and destination being on the same filesystem.
        write_markdown(args.output, markdown, args.overwrite)
        print(report)
        return 0
    except Exception as error:
        print("PDF conversion failed ({}); no success metadata produced.".format(type(error).__name__), file=sys.stderr)
        return 1


def convert_worker(args, source, output):
    """Conversion runs only in the child; metadata travels in a private file."""
    os.umask(0o077)
    images_created = False

    # Some optional packages print diagnostics while importing/converting.
    # Keep normal output small and avoid disclosing document body on errors.
    try:
        converter = importlib.import_module("pymupdf4llm")
        pdf = importlib.import_module("pymupdf")
        with pdf.open(str(source)) as document:
            pages = select_pages(args.pages, len(document))
            sample = pages[:3]
            density = sum(len(document[p].get_text()) for p in sample) / len(sample)
            options = {"pages": pages}
            if args.images:
                args.images.mkdir(mode=0o700, parents=True, exist_ok=False)
                images_created = True
                options.update(write_images=True, image_path=str(args.images.resolve()))
            markdown = converter.to_markdown(document, **options)
            total = len(document)
        if not isinstance(markdown, str):
            raise TypeError("converter did not return Markdown text")
        if args.images:
            protect_images(args.images)
        write_markdown(args._worker_metadata, json.dumps({
            "output": str(output), "pdf_pages": total,
            "selected_pages": [p + 1 for p in pages], "characters": len(markdown),
            "sample_text_characters_per_page": round(density, 1),
            "images": str(args.images.resolve()) if args.images else None,
            "ocr_verified": False,
        }, ensure_ascii=False), overwrite=False)
        # The child only creates the private staged body. The parent owns the
        # final destination and publishes after reading body and metadata.
        write_markdown(output, markdown, overwrite=False)
        return 0
    except ModuleNotFoundError:
        return 3
    except Exception as error:
        print("PDF conversion failed ({}); no success metadata produced.".format(type(error).__name__), file=sys.stderr)
    finally:
        if images_created:
            # Harden any partial images too. The dedicated parent stays private
            # even if the converter produced a non-regular entry we must refuse.
            try:
                protect_images(args.images)
            except Exception:
                pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
