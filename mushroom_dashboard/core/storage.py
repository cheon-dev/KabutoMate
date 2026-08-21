from whitenoise.storage import CompressedManifestStaticFilesStorage


class RelaxedStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False