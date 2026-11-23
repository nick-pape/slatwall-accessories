"""Reusable slatwall hook (verified to fit ProSlat carbon fiber). See slathook.hook."""
from .profile import HOOK, NECK_TOP, SLOT_PITCH, SLOT_OPEN, LIP_T, LIP_RANGE, hook_profile_pts

_SOLIDS = ("hook_face", "hook_part", "hooked_body", "on_side", "fit_test")


def __getattr__(name):            # build123d solids load lazily, so the 2D profile works without a CAD kernel
    if name in _SOLIDS:
        from . import hook
        return getattr(hook, name)
    raise AttributeError(name)
