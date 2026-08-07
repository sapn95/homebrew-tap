#!/usr/bin/env python3
"""Point every formula in this tap at the latest release of its project.

This runs *here*, in the tap, rather than being pushed in from each project.
A workflow may write to its own repository with the token it is given, so a tap
that updates itself needs no secret at all. The alternative, every project
holding a personal access token for this repository, needs one secret per
project, each of which expires, and none of which can be copied from another
because a secret cannot be read back.

Two shapes of formula are handled, because both are in here:

  version "3.0.8"                          a version line, then one url and
  url ".../v3.0.8/thing-macos-arm64.tar.gz"  sha256 pair per platform, all
  sha256 "..."                             pointing at release assets

  url ".../archive/refs/tags/v0.19.1.tar.gz"  no version line, one url and
  sha256 "..."                                sha256 for the source tarball

Nothing is written unless every checksum for that formula was computed from a
download that actually succeeded. A formula with a new version and a stale
checksum is worse than one that was left alone: brew fails at install time with
a mismatch, and the person hitting it has no idea why.

The formula *body* comes from the project too, not only its version. This used
to bump the url and the checksum and leave everything else exactly as it was,
so a project that changed what its formula installs shipped a release where
that change reached nobody. pfadi replaced a shell wrapper with a real command
and added two manual pages; two releases later the tap was still installing the
wrapper, because the tap had never been told. If a project's release carries a
Formula/<name>.rb for itself, that file is now the new formula and only its url
and checksums are rewritten here.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

FORMULA_DIR = Path(__file__).resolve().parent.parent / "Formula"
API = "https://api.github.com"

# github.com/OWNER/REPO, from a url or a homepage line.
REPO_PATTERN = re.compile(r"github\.com/([^/\"]+)/([^/\"]+)")
URL_LINE = re.compile(r'^(\s*)url\s+"([^"]+)"')
SHA_LINE = re.compile(r'^(\s*)sha256\s+"([0-9a-f]{64})"')
VERSION_LINE = re.compile(r'^(\s*)version\s+"([^"]+)"')


def request(url: str, *, binary: bool = False):
    """A GitHub request that identifies itself and uses the token when there is one."""
    headers = {"User-Agent": "sapn95-homebrew-tap-updater"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as response:
        return response.read() if binary else json.loads(response.read())


def latest_tag(owner: str, repo: str) -> str | None:
    """The newest published release, which excludes drafts and prereleases."""
    try:
        return request(f"{API}/repos/{owner}/{repo}/releases/latest")["tag_name"]
    except urllib.error.HTTPError as error:
        # 404 is a project that has never cut a release. Nothing to do, and not
        # a failure: a formula can legitimately sit at head for a while.
        if error.code == 404:
            return None
        raise


def repo_of(text: str) -> tuple[str, str] | None:
    for line in text.splitlines():
        if "url" in line or "homepage" in line:
            match = REPO_PATTERN.search(line)
            if match:
                return match.group(1), match.group(2).removesuffix(".git")
    return None


def current_tag(text: str) -> str | None:
    """The tag the formula points at, from its urls rather than its version line.

    The url is what brew actually fetches. A version line that disagrees with it
    is a bug in the formula, and reading the version would hide it.
    """
    for line in text.splitlines():
        match = URL_LINE.match(line)
        if match:
            tag = re.search(r"/(?:download|tags)/([^/]+)", match.group(2))
            if tag:
                # A release asset url ends at the tag; a source tarball url has
                # the archive name in the same position, so the extension has to
                # come off or the tag becomes "v0.19.1.tar.gz".
                found = tag.group(1)
                for suffix in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".zip"):
                    if found.endswith(suffix):
                        return found[: -len(suffix)]
                return found
    return None


def checksum(url: str) -> str:
    return hashlib.sha256(request(url, binary=True)).hexdigest()


def formula_from_release(owner: str, repo: str, tag: str, name: str) -> str | None:
    """The formula a project keeps for itself, out of its own source tarball.

    Returns None when the project does not carry one, which is the normal case
    for anything that is not packaged by its own repository. The formula in
    this tap is then left as the source of truth for everything but the
    version.
    """
    url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.tar.gz"
    try:
        archive = request(url, binary=True)
    except Exception:  # noqa: BLE001 - a project with no source tarball is fine
        return None

    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            for member in tar.getmembers():
                # <repo>-<tag>/Formula/<name>.rb, and only that: a tarball is
                # somebody else's data, and a path with .. in it or an absolute
                # path is how an archive writes outside where it was extracted.
                parts = Path(member.name).parts
                if len(parts) != 3 or parts[1] != "Formula" or parts[2] != name:
                    continue
                if not member.isfile() or member.size > 200_000:
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    return None
                return handle.read().decode("utf-8")
    except Exception as error:  # noqa: BLE001 - reported, not swallowed
        print(f"{name}: could not read the formula out of {tag}: {error}")
    return None


def rewrite(text: str, old_tag: str, new_tag: str) -> tuple[str, list[str]]:
    """Returns the updated formula and what changed, or raises if a download failed.

    `old_tag` is whatever tag the text being rewritten points at, which is not
    always the tag this tap was on: when the body has just been replaced by the
    project's own copy, that copy trails its repository by one release, because
    the checksum of a tag's tarball cannot be known until the tag exists.
    """
    notes: list[str] = []
    lines = text.splitlines(keepends=True)
    updated: list[str] = []
    pending_sha: str | None = None

    old_version = old_tag.lstrip("v")
    new_version = new_tag.lstrip("v")

    for line in lines:
        version_match = VERSION_LINE.match(line)
        if version_match and version_match.group(2) == old_version:
            updated.append(line.replace(f'"{old_version}"', f'"{new_version}"'))
            notes.append(f"version {old_version} to {new_version}")
            continue

        url_match = URL_LINE.match(line)
        if url_match and old_tag in url_match.group(2):
            new_url = url_match.group(2).replace(old_tag, new_tag)
            # Downloaded now so the checksum below belongs to this exact url.
            # A 404 here raises and the formula is left untouched.
            pending_sha = checksum(new_url)
            updated.append(line.replace(url_match.group(2), new_url))
            notes.append(new_url.rsplit("/", 1)[-1])
            continue

        sha_match = SHA_LINE.match(line)
        if sha_match and pending_sha is not None:
            updated.append(line.replace(sha_match.group(2), pending_sha))
            pending_sha = None
            continue

        updated.append(line)

    if pending_sha is not None:
        raise ValueError("a url had no sha256 line after it")
    return "".join(updated), notes


def main() -> int:
    changed = False
    failed = False

    for path in sorted(FORMULA_DIR.glob("*.rb")):
        text = path.read_text()
        where = repo_of(text)
        if not where:
            print(f"{path.name}: no github repository in it, skipped")
            continue

        owner, repo = where
        old = current_tag(text)
        if not old:
            print(f"{path.name}: no tag in its urls, skipped")
            continue

        try:
            new = latest_tag(owner, repo)
        except Exception as error:  # noqa: BLE001 - reported, not swallowed
            print(f"{path.name}: could not ask {owner}/{repo}: {error}")
            failed = True
            continue

        if not new:
            print(f"{path.name}: {owner}/{repo} has no releases yet")
            continue
        # The project's own copy, when it keeps one, so a release that changed
        # what the formula installs actually reaches the people who installed
        # it. Fetched before the "already at" check on purpose: a formula whose
        # url is current can still have an install block that is two releases
        # behind, which is exactly how this tap shipped a shell wrapper long
        # after the project had replaced it.
        source = formula_from_release(owner, repo, new, path.name)
        base = source if source is not None else text
        base_tag = current_tag(base) or old

        # No shortcut on the tag alone. A formula whose url is already current
        # can still have an install block two releases behind, which is the
        # state this whole thing exists to fix, so the only honest test is
        # whether the rewritten text differs from what is on disk. That is
        # decided after the rewrite, below.

        try:
            updated, notes = rewrite(base, base_tag, new)
            if source is not None and base is not text:
                notes.append("formula from the project")
        except Exception as error:  # noqa: BLE001
            # Left alone on purpose. A new version with a stale checksum fails
            # at install time with a mismatch nobody can explain.
            print(f"{path.name}: {old} to {new} failed, left alone: {error}")
            failed = True
            continue

        # Against what is actually in the file, not against whether a rewrite
        # ran. Comparing the project's copy to the tap's said "different" every
        # hour for a formula the rewrite then turned back into exactly what was
        # already there: nothing to commit, `git commit` exits 1, and every
        # scheduled run went red for a tap that was perfectly up to date.
        if updated == text:
            print(f"{path.name}: already at {new}")
            continue

        path.write_text(updated)
        changed = True
        print(f"{path.name}: {old} to {new} ({', '.join(notes)})")

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"changed={'true' if changed else 'false'}\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
