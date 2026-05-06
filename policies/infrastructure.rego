package swiftdeploy.infrastructure

import future.keywords.if
import future.keywords.in

# Never returns a bare boolean — always carries reasoning.

default allow := false

allow if {
    count(violations) == 0
}

violations contains msg if {
    input.disk_free_gb < data.thresholds.min_disk_free_gb
    msg := sprintf(
        "Disk free %.1fGB is below minimum %.1fGB",
        [input.disk_free_gb, data.thresholds.min_disk_free_gb]
    )
}

violations contains msg if {
    input.cpu_load_1m > data.thresholds.max_cpu_load
    msg := sprintf(
        "CPU 1m load %.2f exceeds maximum %.2f",
        [input.cpu_load_1m, data.thresholds.max_cpu_load]
    )
}

decision := {
    "allow":      allow,
    "violations": violations,
    "domain":     "infrastructure",
    "checked_at": input.timestamp,
    "input_summary": {
        "disk_free_gb": input.disk_free_gb,
        "cpu_load_1m":  input.cpu_load_1m,
    },
}
