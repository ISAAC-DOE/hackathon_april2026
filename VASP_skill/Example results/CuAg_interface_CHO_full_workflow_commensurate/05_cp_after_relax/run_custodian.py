from custodian.custodian import Custodian
from custodian.vasp.handlers import (
    VaspErrorHandler,
    UnconvergedErrorHandler,
    WalltimeHandler,
    FrozenJobErrorHandler,
    MeshSymmetryErrorHandler,
    NonConvergingErrorHandler,
    PositiveEnergyErrorHandler,
)
from custodian.vasp.jobs import VaspJob
from custodian.vasp.validators import VasprunXMLValidator, VaspFilesValidator

handlers = [
    VaspErrorHandler(),
    UnconvergedErrorHandler(),
    WalltimeHandler(buffer_time=300),
    FrozenJobErrorHandler(timeout=1800),
    MeshSymmetryErrorHandler(),
    NonConvergingErrorHandler(),
    PositiveEnergyErrorHandler(),
]

validators = [VasprunXMLValidator(), VaspFilesValidator()]
jobs = [VaspJob(["vasp_std"])]

c = Custodian(
    handlers=handlers,
    jobs=jobs,
    validators=validators,
    max_errors=5,
    max_errors_per_job=5,
    scratch_dir=".",
    gzipped_output=False,
)
c.run()
