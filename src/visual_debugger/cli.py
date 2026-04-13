"""CLI for visual-debugger MCP server."""
import click


@click.group()
@click.version_option()
def main():
    """Visual Debug MCP Server — see running graphics apps through AI eyes."""
    pass


@main.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport (default: stdio)")
@click.option("--display", default=None, help="X11 display (default: $DISPLAY or :0)")
@click.option("--output-dir", default=None, help="Directory for captures (default: /tmp/visual-debugger)")
def serve(transport, display, output_dir):
    """Start the MCP server."""
    from visual_debugger.server import mcp, _wm, _capture

    if display:
        _wm.display = display
        _capture.display = display
    if output_dir:
        from pathlib import Path
        _capture.output_dir = Path(output_dir)
        _capture.output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Starting visual-debugger MCP server (transport={transport})...", err=True)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
