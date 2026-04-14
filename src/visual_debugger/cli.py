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
@click.option("--vlm-backend", type=click.Choice(["auto", "local", "gemini"]), default="auto",
              help="VLM backend: 'local' for HuggingFace model, 'gemini' for API, 'auto' to detect (default: auto)")
@click.option("--vlm-model", default=None,
              help="Model ID for local backend (default: allenai/Molmo2-4B) or Gemini model name")
def serve(transport, display, output_dir, vlm_backend, vlm_model):
    """Start the MCP server."""
    import os
    from visual_debugger import server
    from visual_debugger.analyzer import create_analyzer

    if display:
        server._wm.display = display
        server._capture.display = display
    if output_dir:
        from pathlib import Path
        server._capture.output_dir = Path(output_dir)
        server._capture.output_dir.mkdir(parents=True, exist_ok=True)

    # Override analyzer if explicit backend/model given
    if vlm_backend != "auto" or vlm_model:
        kwargs = {}
        if vlm_backend != "auto":
            kwargs["backend"] = vlm_backend
        elif vlm_model:
            # Infer backend from model name
            if vlm_model.startswith("gemini"):
                kwargs["backend"] = "gemini"
            else:
                kwargs["backend"] = "local"

        if vlm_model:
            if kwargs.get("backend") == "gemini":
                kwargs["model"] = vlm_model
            else:
                kwargs["model_id"] = vlm_model
                os.environ["VLM_MODEL_ID"] = vlm_model

        server._analyzer = create_analyzer(**kwargs)

    backend_name = type(server._analyzer).__name__
    click.echo(f"Starting visual-debugger MCP server (transport={transport}, vlm={backend_name})...", err=True)
    server.mcp.run(transport=transport)


if __name__ == "__main__":
    main()
