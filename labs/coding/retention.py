"""Synthetic planning only: this function never reads or deletes files."""


def expired_names(records, keep_days, restore_verified):
    if type(keep_days) is not int or keep_days < 0:
        raise ValueError("keep_days must be a nonnegative integer")
    if type(restore_verified) is not bool:
        raise ValueError("restore_verified must be Boolean")
    if not restore_verified:
        return []
    return [name for name, age_days in records if age_days >= keep_days]
