# ==============================================================================
# cli.py - command line entry point:  python -m ffai <command>
#
# Commands are wired from day one, but most print "not implemented yet" and
# exit with code 2 until their SPEC step is built (section 14). That lets
# Docker, CI and the README use the final command names already.
# ==============================================================================
import argparse
import time

from loguru import logger

from ffai.config import ConfigError, settings
from ffai.log_config import setup_logging
from ffai.notify import Notifier

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_IMPLEMENTED = 2


def _not_implemented(command: str, step: str) -> int:
    logger.warning(f"'{command}' is not implemented yet ({step})")
    return EXIT_NOT_IMPLEMENTED


def cmd_check(args: argparse.Namespace) -> int:
    # SPEC 6.1: fetch -> analyze -> alerts -> de-dup -> AI -> notify.
    # It also decides by itself whether it is time to run (SPEC 6.2).
    return _not_implemented("check", "SPEC steps 2-5")


def cmd_run(args: argparse.Namespace) -> int:
    """Loop forever: call `check` every CHECK_INTERVAL_SECONDS (Docker CMD)."""
    try:
        while True:
            try:
                rc = cmd_check(argparse.Namespace(dry_run=False))
            except ConfigError:
                raise
            except Exception:  # noqa: BLE001 - one bad cycle must not kill the loop
                logger.exception("check failed")
                rc = EXIT_FAILED
            if rc == EXIT_NOT_IMPLEMENTED:
                return rc  # fail fast instead of looping on a stub
            time.sleep(settings.check_interval_seconds)
    except KeyboardInterrupt:
        return EXIT_OK


def cmd_report(args: argparse.Namespace) -> int:
    return _not_implemented("report", "SPEC steps 2-4")


def cmd_teams(args: argparse.Namespace) -> int:
    return _not_implemented("teams", "SPEC step 2")


def cmd_demo(args: argparse.Namespace) -> int:
    return _not_implemented("demo", "SPEC step 3")


def cmd_serve(args: argparse.Namespace) -> int:
    """Run the local service the Chrome extension talks to."""
    from ffai.service import serve  # imported here so other commands start without it

    try:
        serve(args.port)
    except KeyboardInterrupt:
        return EXIT_OK
    except OSError as e:
        logger.error(f"cannot start the service: {e}. Is another ffai serve already running? Use --port to change it.")
        return EXIT_FAILED
    return EXIT_OK


def cmd_test_notify(args: argparse.Namespace) -> int:
    notifier = Notifier()
    if not notifier.channels:
        logger.warning("No notification channel is configured in .env")
        return EXIT_OK
    names = ", ".join(c.name for c in notifier.channels)
    logger.info(f"Sending a test message to: {names}")
    ok = notifier.send_text("test message", "ffai notification test. If you can read this, the channel works.")
    return EXIT_OK if ok else EXIT_FAILED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ffai", description="ESPN fantasy football alert assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run one check")
    check.add_argument("--dry-run", action="store_true", help="print messages only; no push, nothing recorded")
    check.set_defaults(func=cmd_check)

    serve = sub.add_parser("serve", help="run the local service for the Chrome extension")
    serve.add_argument("--port", type=int, default=None, help="default: SERVICE_PORT (8765)")
    serve.set_defaults(func=cmd_serve)

    sub.add_parser("run", help="loop forever, calling check on a timer").set_defaults(func=cmd_run)
    sub.add_parser("report", help="print the full analysis").set_defaults(func=cmd_report)
    sub.add_parser("teams", help="list all teams and their ids").set_defaults(func=cmd_teams)
    sub.add_parser("test-notify", help="send a test message to every channel").set_defaults(func=cmd_test_notify)
    sub.add_parser("demo", help="run on built-in fake data").set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as e:
        logger.error(str(e))
        return EXIT_FAILED
