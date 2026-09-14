"""Legacy-to-new Ansible variable mapping table for the inventory migration tool.

Entries below were derived by cross-referencing the legacy sample data at
/workspaces/ansible-rework/migrate-test-data against this repo's current
roles/*/defaults/main.yml. Variables with no confirmed new-side equivalent are
intentionally left out of this table so they surface in the tool's unmapped-variable
report instead of being silently guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class VarMigration:
    new_name: str
    # Called on the variable's value if set; returns the migrated value.
    # None means the value is carried over unchanged (pure rename).
    transform: Optional[Callable[[Any], Any]] = None


def list_to_dict_by_key(key_field: str) -> Callable[[Any], dict]:
    """Build a transform converting a list of objects into a dict keyed by one field
    of each object, with the *rest* of the object's fields as the value, e.g.:

        [{"name": "netflow_0", "type": "netflow"}]
        -> {"netflow_0": {"type": "netflow"}}
    """

    def transform(value: Any) -> dict:
        result: dict = {}
        for item in value:
            item = dict(item)
            key = item.pop(key_field)
            result[key] = item
        return result

    return transform


def list_to_dict_by_key_value(key_field: str, value_field: str) -> Callable[[Any], dict]:
    """Build a transform converting a list of objects into a dict keyed by one field
    of each object, using *one specific other field* as the value (discarding any
    other fields on the item), e.g.:

        [{"name": "netflow_0", "config": {"type": "netflow"}}]
        -> {"netflow_0": {"type": "netflow"}}

    Unlike list_to_dict_by_key, this does not wrap the value in a leftover-fields
    dict -- it picks value_field's contents directly.
    """

    def transform(value: Any) -> dict:
        return {item[key_field]: item[value_field] for item in value}

    return transform


# Legacy variable names that should be silently ignored: carried through untouched
# and left out of the unmapped-variable report entirely, rather than flagged as
# needing a mapping decision (they're known no-ops on the new side, not gaps).
IGNORED_VARS: set[str] = {"is_sensor"}

# Legacy variable name *prefixes* that should be silently ignored, same as above --
# covers Ansible's own builtin/magic vars (ansible_host, ansible_user, etc.).
IGNORED_VAR_PREFIXES: tuple[str, ...] = ("ansible_",)


def null_to_empty_list(value: Any) -> Any:
    return [] if value is None else value


def truthy_string_to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("yes", "true", "1")


# sshd_<suffix> (legacy, roles/sensorfleet_daemon_configs) -> sensorfleet_ssh_server_<suffix>
_SSHD_SUFFIXES = [
    "protocol",
    "log_level",
    "x11_forwarding",
    "max_auth_tries",
    "ignore_rhosts",
    "hostbased_authentication",
    "permit_root_login",
    "permit_empty_passwords",
    "permit_user_environment",
    "client_alive_interval",
    "client_alive_count_max",
    "login_grace_time",
    "banner",
    "use_pam",
    "print_motd",
    "challenge_response_authentication",
    "tcp_keepalive",
    "enable_sftp_subsystem",
    "allow_users",
    "allow_groups",
    "deny_users",
    "deny_groups",
    "ciphers",
    "macs",
    "kexalgorithms",
    "additional_configs",
    "usedns",
    "passwordauthentication",
    "allow_tcp_forwarding",
    "max_sessions",
    "max_startups",
]

# Legacy variable name -> migration spec.
LEGACY_TO_NEW_VARS: dict[str, VarMigration] = {
    # sensorfleet_globals
    "sshd_port": VarMigration(new_name="sensorfleet_globals_sshd_port"),
    "sshd_additional_ports": VarMigration(new_name="sensorfleet_globals_sshd_additional_ports"),
    "sensorfleet_usermgmt_enabled": VarMigration(new_name="sensorfleet_globals_usermgmt_enabled"),
    "install_grsec_kernel": VarMigration(new_name="sensorfleet_globals_use_grsec_kernel"),
    "use_fm_repo_service": VarMigration(new_name="sensorfleet_globals_use_fm_repo_service"),
    "use_fm_repo_connection": VarMigration(new_name="sensorfleet_globals_use_fm_repo_service"),
    "vpn_server_port": VarMigration(new_name="sensorfleet_globals_openvpn_server_port"),
    "enable_auditd": VarMigration(new_name="sensorfleet_globals_enable_auditd"),
    # sensorfleet_fleetgram
    "enable_fleetgram_tls": VarMigration(new_name="sensorfleet_fleetgram_enable_tls"),
    "force_initial_sensor_config": VarMigration(new_name="sensorfleet_fleetgram_force_initial_sensor_config"),
    # sensorfleet_license
    "sensorfleet_license": VarMigration(new_name="sensorfleet_license_base64"),
    # sensorfleet_internal_certificates
    "tls_nginx_certificate_verify_depth": VarMigration(
        new_name="sensorfleet_internal_certificates_tls_nginx_certificate_verify_depth"
    ),
    # sensorfleet_kernel
    "audit_backlog_limit": VarMigration(new_name="sensorfleet_kernel_audit_backlog_limit"),
    "disable_kernel_modules": VarMigration(new_name="sensorfleet_kernel_disabled_modules"),
    "disable_usb_storage": VarMigration(new_name="sensorfleet_kernel_disable_usb_storage"),
    # sensorfleet_logging
    "sensorfleet_loghost_host": VarMigration(new_name="sensorfleet_logging_loghost_host"),
    "sensorfleet_loghost_port": VarMigration(new_name="sensorfleet_logging_loghost_port"),
    "sensorfleet_loghost_transport": VarMigration(new_name="sensorfleet_logging_loghost_transport"),
    "sensorfleet_loghost_syslogprotocol_flag": VarMigration(
        new_name="sensorfleet_logging_loghost_syslogprotocol_flag"
    ),
    "sensorfleet_loghost_tls_key": VarMigration(new_name="sensorfleet_logging_loghost_tls_key"),
    "sensorfleet_loghost_tls_cert": VarMigration(new_name="sensorfleet_logging_loghost_tls_cert"),
    "sensorfleet_loghost_tls_ca": VarMigration(new_name="sensorfleet_logging_loghost_tls_ca"),
    "sensorfleet_loghost_tls_verify": VarMigration(new_name="sensorfleet_logging_loghost_tls_verify"),
    "sensorfleet_loghost_tls_ssloptions": VarMigration(new_name="sensorfleet_logging_loghost_tls_ssloptions"),
    "sensorfleet_loghost_tls_ca_additional": VarMigration(
        new_name="sensorfleet_logging_loghost_tls_ca_additional"
    ),
    "sensorfleet_loghost_enable_disk_buffer": VarMigration(
        new_name="sensorfleet_logging_loghost_enable_disk_buffer"
    ),
    "sensorfleet_loghost_disk_buffer_size": VarMigration(
        new_name="sensorfleet_logging_loghost_disk_buffer_size"
    ),
    "sensorfleet_loghost_disk_buffer_reliable": VarMigration(
        new_name="sensorfleet_logging_loghost_disk_buffer_reliable"
    ),
    "sensorfleet_loghost_disk_buffer_membuf_size": VarMigration(
        new_name="sensorfleet_logging_loghost_disk_buffer_membuf_size"
    ),
    "sensorfleet_loghost_disk_buffer_membuf_length": VarMigration(
        new_name="sensorfleet_logging_loghost_disk_buffer_membuf_length"
    ),
    "enable_sensorfleet_component_audit": VarMigration(new_name="sensorfleet_logging_enable_component_audit"),
    "enable_sensorfleet_instrument_audit": VarMigration(new_name="sensorfleet_logging_enable_instrument_audit"),
    # sensorfleet_services_ntp
    "sensorfleet_fm_ntp_pools": VarMigration(new_name="sensorfleet_services_ntp_pools"),
    "sensorfleet_fm_ntp_servers": VarMigration(new_name="sensorfleet_services_ntp_servers"),
    # sensorfleet_nginx
    "nginx_sensorui_vhost_ssl_cert_path": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_cert_path"),
    "nginx_sensorui_vhost_ssl_key_path": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_key_path"),
    "nginx_sensorui_vhost_ssl_cert": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_cert"),
    "nginx_sensorui_vhost_ssl_key": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_key"),
    "nginx_sensorui_vhost_ssl_protocols": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_protocols"),
    "nginx_sensorui_vhost_ssl_ciphers": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_ciphers"),
    "nginx_sensorui_vhost_ssl_ecdh_curve": VarMigration(
        new_name="sensorfleet_nginx_sensorui_vhost_ssl_ecdh_curve"
    ),
    "nginx_sensorui_vhost_ssl_prefer_server_ciphers": VarMigration(
        new_name="sensorfleet_nginx_sensorui_vhost_ssl_prefer_server_ciphers"
    ),
    "nginx_sensorui_vhost_ssl_dhparams": VarMigration(new_name="sensorfleet_nginx_sensorui_vhost_ssl_dhparams"),
    "nginx_sensorui_vhost_ssl_dhparams_path": VarMigration(
        new_name="sensorfleet_nginx_sensorui_vhost_ssl_dhparams_path"
    ),
    # sensorfleet_openvpn
    "vpn_server_host": VarMigration(new_name="sensorfleet_openvpn_server_host"),
    "vpn_server_connect_ip": VarMigration(new_name="sensorfleet_openvpn_server_connect_ip"),
    "vpn_client_ip": VarMigration(new_name="sensorfleet_openvpn_client_ip"),
    "vpn_tls_cipher": VarMigration(new_name="sensorfleet_openvpn_tls_cipher"),
    "vpn_cipher": VarMigration(new_name="sensorfleet_openvpn_cipher"),
    "vpn_dhparams": VarMigration(new_name="sensorfleet_openvpn_dhparams"),
    "vpn_crl_verify": VarMigration(new_name="sensorfleet_openvpn_crl_verify"),
    "vpn_require_key_usage_in_certificate": VarMigration(
        new_name="sensorfleet_openvpn_require_key_usage_in_certificate"
    ),
    "vpn_push_routes_v4": VarMigration(new_name="sensorfleet_openvpn_push_routes_v4"),
    # sensorfleet_repos
    "ubuntu_release": VarMigration(new_name="sensorfleet_repos_os_release"),
    "system_repository_source": VarMigration(new_name="sensorfleet_repos_repository_os"),
    "sensorfleet_apt_release": VarMigration(new_name="sensorfleet_repos_apt_release"),
    "sensorfleet_apt_auth_user": VarMigration(new_name="sensorfleet_repos_repository_login"),
    "sensorfleet_apt_auth_pass": VarMigration(new_name="sensorfleet_repos_repository_password"),
    # sensorfleet_system
    "apt_extra_packages": VarMigration(new_name="sensorfleet_system_extra_packages"),
    "shell_session_timeout": VarMigration(new_name="sensorfleet_system_shell_session_timeout"),
    "sudo_logfile": VarMigration(new_name="sensorfleet_system_sudo_logfile"),
    "journald_storage": VarMigration(new_name="sensorfleet_system_journald_storage"),
    "journald_compress": VarMigration(
        new_name="sensorfleet_system_journald_compress", transform=truthy_string_to_bool
    ),
    "enable_audit_root_commands": VarMigration(new_name="sensorfleet_system_enable_root_command_logging"),
    "disable_allow_auth_import": VarMigration(new_name="sensorfleet_system_disable_allow_auth_import"),
    "disable_allow_adoption_import": VarMigration(new_name="sensorfleet_system_disable_allow_adoption_import"),
    # sensorfleet_firewall
    "sensorfleet_allow_ssh_from_anywhere": VarMigration(new_name="sensorfleet_firewall_allow_ssh_from_anywhere"),
    "sensorfleet_ipv6_autoconfig": VarMigration(new_name="sensorfleet_firewall_ipv6_autoconfig"),
    "sensorfleet_ferm_rules": VarMigration(
        new_name="sensorfleet_firewall_ferm_rules", transform=null_to_empty_list
    ),
    # sensorfleet_system_cacerts
    "cacerts_use_os_default_certs": VarMigration(new_name="sensorfleet_system_cacerts_use_os_default_certs"),
    "cacerts_trust_new_os_certs": VarMigration(new_name="sensorfleet_system_cacerts_cacerts_trust_new_os_certs"),
    "custom_ca_certs_add": VarMigration(new_name="sensorfleet_system_cacerts_custom_ca_certs"),
    # sensorfleet_config
    "sensorfleet_sensor_retention_rules": VarMigration(new_name="sensorfleet_config_default_retention_rules"),
    "sensorfleet_bridges": VarMigration(new_name="sensorfleet_config_bridges"),
    "sensorfleet_homenets": VarMigration(new_name="sensorfleet_config_homenets"),
    # sensorfleet_instruments
    "sensorfleet_instruments": VarMigration(
        new_name="sensorfleet_instruments_group", transform=list_to_dict_by_key_value("name", "config")
    ),
    "sensorfleet_instruments_host": VarMigration(
        new_name="sensorfleet_instruments_host", transform=list_to_dict_by_key_value("name", "config")
    ),
    "sensorfleet_instrument_configs": VarMigration(new_name="sensorfleet_instruments_instrument_configs_host"),
    # sensorfleet_usermgmt (identity renames -- already the same name on both sides)
    "sensorfleet_usermgmt_credential_dir": VarMigration(new_name="sensorfleet_usermgmt_credential_dir"),
    "sensorfleet_usermgmt_default_password": VarMigration(new_name="sensorfleet_usermgmt_default_password"),
    "sensorfleet_usermgmt_ui_force_password_change": VarMigration(
        new_name="sensorfleet_usermgmt_ui_force_password_change"
    ),
    # sensorfleet_ssh (mechanical sshd_<suffix> -> sensorfleet_ssh_server_<suffix> prefix swap)
    **{
        f"sshd_{suffix}": VarMigration(new_name=f"sensorfleet_ssh_server_{suffix}")
        for suffix in _SSHD_SUFFIXES
    },
}
