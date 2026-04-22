# This script manages the add-on's assets (CSS and JavaScript files).
# Its primary responsibilities are:
# 1. Defining which assets the add-on requires.
# 2. Syncing these assets from the add-on's installation folder to Anki's media folder. So mobile can render code as well
# 3. Generating the necessary HTML to include these assets in Anki card templates.

from pathlib import Path
from aqt import mw
from . import utils
from . import config # Need config access here

CSS_FILES = [
    "codemirror/lib/codemirror.css",
    "styles/reviewer_style.css",
]

# Base JS files that are always required
CORE_JS_FILES = [
    "codemirror/lib/codemirror.js",
    "codemirror/addon/runmode/runmode.js",
    "codemirror/mode/meta.js"
]

PREFIX = "_codemirror_anki_"

def get_prefixed_filename(path: Path) -> str:
    return f"{PREFIX}{path.name}"

def _sync_file(source_path: Path, media_dir: Path):
    """
    Core logic for syncing a single asset file to Anki's media folder.

    This function implements a "delete-then-write" strategy to ensure assets are
    always up-to-date and to work around Anki's media hashing behavior. Anki
    may create files with a hash in the name (e.g., 'style-abc123.css') if it
    detects content changes. To prevent accumulation of old, hashed files, this
    function proactively removes all variants of the target file before writing
    the new version.
    """
    if not source_path.exists():
        return

    prefixed_name = get_prefixed_filename(source_path)
    base_name = Path(prefixed_name).stem
    extension = Path(prefixed_name).suffix

    # Create a glob pattern to find all existing versions of the asset.
    # e.g., for '_codemirror_anki_reviewer_style.css', the pattern is
    # '_codemirror_anki_reviewer_style*.css' to match hashed versions.
    glob_pattern = f"{base_name}*{extension}"
    
    # Use standard Pathlib to glob for files on the filesystem, which is more
    # stable across different Anki versions than relying on internal media DB methods.
    files_on_disk = media_dir.glob(glob_pattern)
    filenames_to_remove = [p.name for p in files_on_disk]

    # If any old versions are found, use Anki's API to remove them.
    # This ensures they are properly removed from the media database as well.
    if filenames_to_remove:
        mw.col.media.trash_files(filenames_to_remove)

    # Read the new file's content and write it using Anki's media API.
    # mw.col.media.write_data handles adding the file to the media database
    # and marking it for synchronization with AnkiWeb.
    data = source_path.read_bytes()
    mw.col.media.write_data(prefixed_name, data)

def get_all_js_files():
    supported_langs = config.CONFIG.get(config.CONFIG_KEY_LANGUAGES, ["python", "javascript", "clike", "css", "htmlmixed"])
    
    mode_files = []
    # Safe load: Only sync files that exist
    for lang in supported_langs:
        mode_path = utils.USER_FILES_PATH / "codemirror" / "mode" / lang / f"{lang}.js"
        if mode_path.exists():
            mode_files.append(f"codemirror/mode/{lang}/{lang}.js")
    
    return CORE_JS_FILES + mode_files + ["scripts/reviewer_script.js"]


def sync_assets_to_media_folder():
    media_dir = Path(mw.col.media.dir())
    addon_dir = utils.USER_FILES_PATH
    # Use dynamic JS files list here
    files_to_sync = CSS_FILES + get_all_js_files()

    for relative_path_str in files_to_sync:
        source_path = addon_dir / relative_path_str
        _sync_file(source_path, media_dir)


def sync_theme_to_media_folder(theme_name: str):
    """
    Syncs a single, dynamically chosen CodeMirror theme file to the media folder.
    """
    media_dir = Path(mw.col.media.dir())
    theme_path = utils.USER_FILES_PATH / "codemirror" / "theme" / f"{theme_name}.css"
    _sync_file(theme_path, media_dir)


def get_mobile_resources_html(theme_name: str) -> str:
    sync_assets_to_media_folder()
    sync_theme_to_media_folder(theme_name)
    
    css_links = ""
    for file in CSS_FILES:
        filename = get_prefixed_filename(Path(file))
        css_links += f'<link rel="stylesheet" type="text/css" href="{filename}">'
    
    theme_filename = get_prefixed_filename(Path(f"{theme_name}.css"))
    css_links += f'<link rel="stylesheet" type="text/css" href="{theme_filename}">'

    js_links = ""
    # Call the new dynamic list builder here as well
    for file in get_all_js_files():
        filename = get_prefixed_filename(Path(file))
        js_links += f'<script src="{filename}"></script>'

    return f"""
    <div id="{PREFIX}resources" style="display: none;">
        {css_links}
        <script>window.CODE_MIRROR_GLOBAL_THEME = "{theme_name}";</script>
        {js_links}
    </div>
    """
