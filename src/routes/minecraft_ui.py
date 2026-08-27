import os
from pathlib import Path

from sanic import Blueprint, response
from sanic.exceptions import NotFound

# Create two blueprints: one for the UI route and one for static files
minecraft_ui_blueprint = Blueprint('minecraft_ui', url_prefix='/minecraft')
static_files_blueprint = Blueprint('static_files')  # No prefix to serve files from root

# Get the absolute path to the public directory
PUBLIC_DIR = str(Path(__file__).parent.parent.parent / 'public')
MINECRAFT_UI_DIR = str(Path(PUBLIC_DIR) / 'minecraft-ui')


@minecraft_ui_blueprint.route('/')
async def minecraft_ui(request):
    """Serve the Minecraft-style UI."""
    return await response.file(os.path.join(MINECRAFT_UI_DIR, 'index.html'))


@minecraft_ui_blueprint.route('/<path:path>')
async def minecraft_ui_static(request, path):
    """Serve static files for the Minecraft UI."""
    file_path = os.path.join(MINECRAFT_UI_DIR, path)
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise NotFound(f"File {path} not found")
    
    return await response.file(file_path)


# Utility function to check if a font exists and download it if it doesn't
@minecraft_ui_blueprint.route('/check-fonts')
async def check_fonts(request):
    """Check if the Minecraft fonts exist and create placeholders if they don't."""
    font_dir = Path(MINECRAFT_UI_DIR) / 'fonts'
    font_dir.mkdir(exist_ok=True)
    
    # Check for minecraft-ten.woff2 font
    minecraft_ten = font_dir / 'minecraft-ten.woff2'
    if not minecraft_ten.exists():
        # Create a placeholder file with a message
        minecraft_ten.touch()
        with open(minecraft_ten, 'w') as f:
            f.write('# Placeholder for Minecraft Ten font.\n')
    
    # Check for minecraft-seven.woff2 font
    minecraft_seven = font_dir / 'minecraft-seven.woff2'
    if not minecraft_seven.exists():
        # Create a placeholder file with a message
        minecraft_seven.touch()
        with open(minecraft_seven, 'w') as f:
            f.write('# Placeholder for Minecraft Seven font.\n')
    
    return response.json({
        "message": "Font check completed. You'll need to replace the placeholder font files with real Minecraft-style fonts.",
        "minecraft_ten": str(minecraft_ten),
        "minecraft_seven": str(minecraft_seven)
    })


# Static file routes
@static_files_blueprint.route('/minecraft-ui/<path:path>')
async def serve_minecraft_ui_files(request, path):
    """Serve static files from minecraft-ui directory."""
    file_path = os.path.join(MINECRAFT_UI_DIR, path)
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise NotFound(f"File {path} not found")
    
    return await response.file(file_path)


@static_files_blueprint.route('/geode_logo.png')
async def serve_logo(request):
    """Serve the Geode logo."""
    logo_path = os.path.join(PUBLIC_DIR, 'geode_logo.png')
    
    if not os.path.exists(logo_path) or not os.path.isfile(logo_path):
        raise NotFound("Logo file not found")
    
    return await response.file(logo_path)