"""DSUL - Disturb State USB Light : Module initialization."""

import pkg_resources

try:
    VERSION = pkg_resources.get_distribution("dsul").version
except pkg_resources.DistributionNotFound:
    VERSION = "0.0.0"  # fallback if version can't be read

DEBUG = False
