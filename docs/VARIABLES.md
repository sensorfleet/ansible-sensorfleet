# Variable reference

Every variable meant to be set by every role, one section per role. If a role isn't listed here, it defines no configurable variables (see [Roles with no configurable variables](#roles-with-no-configurable-variables) at the bottom). A handful of variables that exist in a role's `defaults/main.yml` but aren't meant to be touched (e.g. legacy leftovers not yet wired up to anything) are intentionally omitted rather than documented as if they had an effect.

Roles are listed in the order [`playbooks/sensorfleet.yml`](../playbooks/sensorfleet.yml) runs them, which is also the order used in the [main README's roles table](../README.md#roles-overview). Every variable is prefixed with its role's name (`sensorfleet_<role>_*`), per the convention in [`AGENTS.md`](../AGENTS.md). Set these the same way as any other Ansible variable — inventory `hosts.yml` vars, or `group_vars`/`host_vars` files (see the [README's inventory setup section](../README.md#inventory-setup)).

**Legend**

| Column | Meaning |
|---|---|
| Variable | Exact name as used in code. |
| Default | The literal value from the role's `defaults/main.yml`. |
| Type | Inferred type/valid values. `null` almost always means "unset" — most `null`-defaulted variables disable or skip a whole feature until a value is given. |
| Description | What the variable actually controls, based on the tasks/templates that consume it (there are no inline comments in the source to draw from). |

---

## sensorfleet_globals

Shared defaults with no tasks of its own — every variable here is consumed by *other* roles' tasks/templates, not by this role.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_globals_sshd_port` | `22` | int | The sshd listen port. Rendered into `Port` in `sshd_config` by `sensorfleet_ssh`, and opened in the firewall's early-rules fragment by `sensorfleet_firewall` (only added as an extra firewall rule if it differs from 22, since 22 is always allowed when `sensorfleet_firewall_allow_ssh_from_anywhere` is true). |
| `sensorfleet_globals_sshd_additional_ports` | `[]` | list of int | Extra sshd listen ports, each rendered as an additional `Port` line in `sshd_config` and opened in the firewall. |
| `sensorfleet_globals_use_grsec_kernel` | `false` | bool | If true, `sensorfleet_kernel` also installs the `linux-fleet-grsec` package, and `sensorfleet_sysctl` layers `sensorfleet_sysctl_grsec_defaults` on top of the base sysctl defaults. |
| `sensorfleet_globals_enable_auditd` | `true` | bool | Enables/starts (or disables/stops) the `auditd` service in `sensorfleet_system`. |
| `sensorfleet_globals_use_fm_repo_service` | `true` | bool | Selects the apt repository strategy in `sensorfleet_repos`: `true` relays repository access through the FM's proxy service (`fleet repository enable-proxy`); `false` configures direct access to the upstream repositories with the credentials below. Also gates `sensorfleet_sanity_checks`' assertion that repository credentials are defined. |
| `sensorfleet_globals_openvpn_server_port` | `1194` | int | The UDP port the FM's OpenVPN server listens on and sensors connect to. Rendered into both the OpenVPN server/client configs (`sensorfleet_openvpn`) and the firewall's OpenVPN rule fragment (`sensorfleet_firewall`). |
| `sensorfleet_globals_fleet_retries` | `5` | int | Retry count for `fleet` CLI commands (`fleet config show`/`write`) used by `sensorfleet_config` and `sensorfleet_instruments`. |
| `sensorfleet_globals_fleet_retry_delay_seconds` | `3` | int | Delay in seconds between the retries above. |
| `sensorfleet_globals_apt_lock_retries` | `100` | int | Retry count for `apt`/apt-lock-sensitive tasks across many roles (`sensorfleet_system`, `sensorfleet_kernel`, `sensorfleet_services_ntp`, `sensorfleet_prepare_ubuntu`, `sensorfleet_prepare_role`, `sensorfleet_repos`'s handler). Ansible-base 2.10.8 doesn't support the module-level `lock_timeout` parameter, hence the manual `until`/`retries`/`delay` pattern instead. |
| `sensorfleet_globals_apt_lock_retry_delay_seconds` | `15` | int | Delay in seconds between the retries above. |

## sensorfleet_sanity_checks

Runs (tagged `always`) before any provisioning: verifies the host's identity and clock, and clears any pre-existing apt lock.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_sanity_checks_max_clock_skew_seconds` | `300` | int | Maximum allowed difference, in seconds, between the target host's clock and the Ansible controller's clock. If exceeded, the run fails (unless corrected — see below). |
| `sensorfleet_sanity_checks_clock_from_ansible_controller` | `false` | bool | If true and the clock is out of sync, sets the target host's clock from the controller's clock (`date -u --set=...`) instead of failing the run. |

## sensorfleet_internal_certificates

Manages internal (mutual-TLS) certificates issued by the FM's internal CA (`fleetcert`), used for FM↔sensor communication.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_internal_certificates_tls_nginx_certificate_verify_depth` | `100` | int | Certificate chain verification depth passed into nginx's internal-communication TLS client-verification config (`ssl_verify_depth`/proxy TLS auth verify depth). |

## sensorfleet_openvpn

Configures the OpenVPN tunnel that carries FM↔sensor traffic: server config/CA-signed certs on `fleetmgmt`, client config on `sensors`.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_openvpn_server_host` | `"{{ groups['fleetmgmt'][0] }}"` | string (Jinja expression, not a plain literal) | The FM inventory hostname, used to `delegate_to` the FM host for certificate-signing tasks. Defaults to the first host in the `fleetmgmt` group rather than a static value — override only if certificate signing should be delegated elsewhere. |
| `sensorfleet_openvpn_tls_cipher` | `TLS-ECDHE-ECDSA-WITH-AES-256-GCM-SHA384` | string | The `tls-cipher` value in both the OpenVPN server and client configs (controls TLS handshake cipher suite). |
| `sensorfleet_openvpn_cipher` | `AES-256-CBC` | string | The `cipher` (data channel encryption) value in both the OpenVPN server and client configs. |
| `sensorfleet_openvpn_dhparams` | `null` | string (PEM content) or `null` | Diffie-Hellman parameters for the OpenVPN server. `null` leaves it unconfigured; a PEM string enables DH params in the server config. |
| `sensorfleet_openvpn_crl_verify` | `null` | string (path) or `null` | Path to a certificate revocation list for the OpenVPN server to check (`crl-verify`). `null` disables CRL checking. |
| `sensorfleet_openvpn_require_key_usage_in_certificate` | `true` | bool | Enables the `remote-cert-tls`/key-usage requirement so client certificates must carry the expected key usage extension. |
| `sensorfleet_openvpn_push_routes_v4` | `[]` | list of strings (CIDR/route entries) | Additional IPv4 routes the OpenVPN server pushes to connecting sensor clients. |

## sensorfleet_system_cacerts

Manages which CA certificates the OS trusts, via `ca-certificates` debconf settings plus a custom CA directory.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_system_cacerts_use_os_default_certs` | `true` | bool | If false, deselects every entry in `/etc/ca-certificates.conf` (comments them all out) and clears the `ca-certificates/enable_crts` debconf value, so only custom CA certs below are trusted — the distro-provided CA bundle is not. |
| `sensorfleet_system_cacerts_cacerts_trust_new_os_certs` | `true` | bool | Sets the `ca-certificates/trust_new_certs` debconf value (`yes`/`no`) — whether newly-installed OS CA certificate packages are trusted automatically without prompting. |
| `sensorfleet_system_cacerts_custom_ca_certs` | `[]` | list of `{name, certificate}` objects | Extra CA certificates to install into `/usr/local/share/ca-certificates/ansible/<name>.crt` and trust. Any previously-installed custom cert not present in this list on a later run is removed. |

## sensorfleet_repos

Sets up apt access to the SensorFleet and OS mirror repositories, either relayed through the FM or direct from sensors.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_repos_apt_release` | `master` | string | The SensorFleet apt release/channel name, passed to `fleet repository set --release`. |
| `sensorfleet_repos_os_release` | `jammy` | string | The Ubuntu codename used for the OS mirror repository (`--os-codename`, used in direct-access mode only). |
| `sensorfleet_repos_repository_fleet` | `https://repository.sensorfleet.com/fleet` | string (URL) | Upstream URL for the SensorFleet package repository. |
| `sensorfleet_repos_repository_os` | `https://repository.sensorfleet.com/ubuntu-mirror` | string (URL) | Upstream URL for the OS package mirror. |
| `sensorfleet_repos_repository_login` | `null` | string or `null` | Repository auth username. Required (asserted by `sensorfleet_sanity_checks`) on `fleetmgmt` hosts, or on any host when `sensorfleet_globals_use_fm_repo_service` is false. When set together with the password below, direct-access mode also writes apt auth config (`/etc/apt/auth.conf.d/sensorfleet.conf`); FM-relay mode passes both as upstream credentials to `fleet repository enable-proxy`. |
| `sensorfleet_repos_repository_password` | `null` | string or `null` | Repository auth password, paired with the login above. |

## sensorfleet_services_ntp

Configures time synchronization: chrony as an NTP server on `fleetmgmt`, systemd-timesyncd as a client on `sensors`. The pool/server/maxdistance variables only apply to the `fleetmgmt` (chrony) side. In some environments if facing issues where NTP sync does not work check chrony/timesyncd logs and adjust `sensorfleet_services_ntp_maxdistance` as needed.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_services_ntp_pools` | 4 Ubuntu NTP pool entries, each `{host, options}` | list of `{host, options}` objects | NTP `pool` lines for chrony's config on `fleetmgmt` — the upstream time source pools and their chrony options string (e.g. `iburst maxsources N`). |
| `sensorfleet_services_ntp_servers` | `[]` | list | Additional individual NTP `server` entries for chrony, alongside the pools above. |
| `sensorfleet_services_ntp_maxdistance` | `5` | int (seconds) | chrony's `maxdistance` setting — the maximum acceptable root distance for a time source to be considered usable. |

## sensorfleet_kernel

Installs the SensorFleet kernel package(s) and disables a set of kernel modules considered unnecessary/risky. SensorFleet shipped kernel has already had some of these modules removed but we still install these rules to satisfy some of automated auditing tools.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_kernel_audit_backlog_limit` | `8192` | int | Sets the kernel `audit_backlog_limit` boot parameter (queued-but-unprocessed audit event limit) via EFI kernel command-line configuration, when applicable. |
| `sensorfleet_kernel_disabled_modules` | `[tipc, rds, cramfs, udf, sctp, dccp]` | list of strings | Kernel module names to blacklist via `/etc/modprobe.d/sensorfleet_disable_modules.conf` — uncommon protocol/filesystem modules disabled to shrink attack surface. |
| `sensorfleet_kernel_disable_usb_storage` | `false` | bool | If true, adds `usb-storage` to the disabled-modules list above (blocking USB mass-storage devices). |

## sensorfleet_sysctl

Applies sysctl values, merged from three layers: base defaults, optional grsec-kernel defaults, then user overrides (each layer overrides keys from the one before it).

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_sysctl_defaults` | 5 keys — network buffer sizing (`net.core.wmem_default/max`, `net.core.netdev_max_backlog/budget`) and `kernel.panic: 10` | map of sysctl key → value | Baseline sysctl values applied on every host. |
| `sensorfleet_sysctl_grsec_defaults` | 3 `kernel.grsecurity.*` keys, all `0` | map of sysctl key → value | Additional sysctl values layered on top of the defaults above, only when `sensorfleet_globals_use_grsec_kernel` is true. |
| `sensorfleet_sysctl_overrides` | `{}` | map of sysctl key → value | User-supplied overrides, applied last — takes precedence over both of the above for any overlapping key. |

## sensorfleet_system

General host hardening and OS-level configuration: package installation, root password, security lockdown flags, journald/shell/sudo/lxd settings.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_system_root_password` | `null` | string (crypted password hash) or `null` | If set, applied as the root account's password hash (via `ansible.builtin.user`'s `password` parameter, which expects a `crypt(3)`-style hash, never a plaintext password). `null` leaves the existing root password untouched. Generate a hash with `mkpasswd --method=sha-512` (from the `whois` package), or `python3 -c "import crypt; print(crypt.crypt('mypassword', crypt.mksalt(crypt.METHOD_SHA512)))"`, or Ansible's own `password_hash` filter, e.g. `{{ 'mypassword' | password_hash('sha512') }}`. |
| `sensorfleet_system_extra_packages` | `[]` | list of strings | Additional apt packages to install beyond the base set. |
| `sensorfleet_system_disable_allow_auth_import` | `true` | bool | If true, removes `/etc/sensorfleet/allow_auth_import`, disabling the ability to import authentication configuration via the UI/CLI import mechanism. |
| `sensorfleet_system_disable_allow_adoption_import` | `true` | bool | If true, removes `/etc/sensorfleet/allow_adoption_import`, disabling the ability to import fleet-adoption configuration the same way. |
| `sensorfleet_system_enable_root_command_logging` | `true` | bool | If true, installs an auditd rule (`sensorfleet_root_command_logging.rules`) that logs every `execve` performed as root (uid 0), tagged `rootcmd`. |
| `sensorfleet_system_shell_session_timeout` | `null` | int (seconds) or `null` | If set, installs `/etc/profile.d/02-session-timeout.sh` to auto-logout idle interactive shells after this many seconds; `null` removes that file (no timeout). |
| `sensorfleet_system_sudo_logfile` | `null` | string (path) or `null` | If set, configures sudo (`Defaults logfile=...`) to log all sudo invocations to this file; `null` removes that sudoers.d fragment. |
| `sensorfleet_system_journald_storage` | `persistent` | string (`volatile`\|`persistent`\|`auto`\|`none`) | journald's `Storage=` setting, rendered directly into `/etc/systemd/journald.conf.d/00-sensorfleet.conf`. |
| `sensorfleet_system_journald_compress` | `true` | bool | journald's `Compress=` setting. |
| `sensorfleet_system_journald_cleanup_unmanaged_files` | `true` | bool | If true, removes any file in `/etc/systemd/journald.conf.d/` other than the one this role manages (`00-sensorfleet.conf`) — i.e. sweeps up drop-ins not owned by this role. |

## sensorfleet_logging

Configures forwarding of local logs to a remote syslog-ng loghost, and toggles two component-level audit-logging defines consumed elsewhere.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_logging_loghost_host` | `null` | string (hostname/IP) or `null` | Remote loghost address. Combined with the transport setting below to decide whether remote forwarding is configured at all. |
| `sensorfleet_logging_loghost_port` | `514` | int | Remote loghost port. |
| `sensorfleet_logging_loghost_transport` | `null` | string (`tcp`\|`udp`\|`tls`) or `null` | Selects which syslog-ng config fragment gets installed (`loghost_tcp.yml`/`loghost_udp.yml`/`loghost_tls.yml`). Any other value (including `null`) removes the remote-logging config entirely — no forwarding. |
| `sensorfleet_logging_loghost_syslogprotocol_flag` | `false` | bool | Enables the syslog-ng `syslog-protocol` flag on the remote destination (RFC 5424 framing) instead of legacy BSD syslog framing. |
| `sensorfleet_logging_loghost_tls_key` | `null` | string (PEM content) or `null` | TLS client private key, installed to `/etc/syslog-ng/tls/key.pem` when set. Only relevant when transport is `tls`. |
| `sensorfleet_logging_loghost_tls_cert` | `null` | string (PEM content) or `null` | TLS client certificate, installed to `/etc/syslog-ng/tls/cert.pem` when set. |
| `sensorfleet_logging_loghost_tls_ca` | `null` | string (PEM content) or `null` | TLS CA certificate used to verify the loghost, installed as `/etc/syslog-ng/tls/ca.d/ca.pem` when set. |
| `sensorfleet_logging_loghost_tls_verify` | `true` | bool | Whether syslog-ng verifies the loghost's TLS certificate against the CA(s) above. |
| `sensorfleet_logging_loghost_tls_ssloptions` | `null` | string or `null` | Passed through as syslog-ng's `ssl-options()` value (TLS protocol/option tuning) when set. |
| `sensorfleet_logging_loghost_tls_ca_additional` | `[]` | list of `{name, certificate}` objects | Additional trusted CA certificates beyond the single `tls_ca` above, each installed as `/etc/syslog-ng/tls/ca.d/<name>.pem`. All CA certs in `ca.d/` are hashed (`openssl x509 -hash`) and symlinked the way OpenSSL expects for CA-directory lookups; files/symlinks not corresponding to a currently-configured CA are cleaned up automatically. |
| `sensorfleet_logging_loghost_enable_disk_buffer` | `false` | bool | Enables syslog-ng's disk-based buffering for the remote destination (so log delivery survives a network outage), sized/tuned by the four `disk_buffer_*` variables below. Only meaningful for TCP/TLS destinations. |
| `sensorfleet_logging_loghost_disk_buffer_size` | `1073741824` (1 GiB) | int (bytes) | Maximum size of the on-disk buffer file. |
| `sensorfleet_logging_loghost_disk_buffer_reliable` | `false` | bool | syslog-ng disk-buffer "reliable" mode — trades throughput for stronger delivery guarantees (messages are fsynced before being acknowledged). |
| `sensorfleet_logging_loghost_disk_buffer_membuf_size` | `163840000` | int (bytes) | Size of the in-memory buffer syslog-ng uses in front of the disk buffer. |
| `sensorfleet_logging_loghost_disk_buffer_membuf_length` | `10000` | int (messages) | Max number of messages held in that in-memory buffer. |
| `sensorfleet_logging_enable_component_audit` | `true` | bool | Defines `ENABLE_SF_COMPONENT_AUDIT` as `"true"` for syslog-ng, gating whether SensorFleet component audit logging is emitted. |
| `sensorfleet_logging_enable_instrument_audit` | `true` | bool | Defines `ENABLE_SF_INSTRUMENT_AUDIT` as `"true"` for syslog-ng, gating whether instrument audit logging is emitted. |

## sensorfleet_ssh

Renders `/etc/ssh/sshd_config` (validated with `sshd -t` before being applied) and the SSH login banner. Most variables map 1:1 onto an sshd directive of the same intent.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_ssh_server_protocol` | `2` | int | sshd `Protocol`. |
| `sensorfleet_ssh_server_log_level` | `VERBOSE` | string (sshd `LogLevel` enum) | sshd `LogLevel`. |
| `sensorfleet_ssh_server_x11_forwarding` | `false` | bool | sshd `X11Forwarding`. |
| `sensorfleet_ssh_server_max_auth_tries` | `4` | int | sshd `MaxAuthTries`. |
| `sensorfleet_ssh_server_ignore_rhosts` | `true` | bool | sshd `IgnoreRhosts`. |
| `sensorfleet_ssh_server_hostbased_authentication` | `false` | bool | sshd `HostbasedAuthentication`. |
| `sensorfleet_ssh_server_permit_root_login` | `without-password` | string (sshd `PermitRootLogin` enum: `yes`\|`without-password`\|`prohibit-password`\|`forced-commands-only`\|`no`) | sshd `PermitRootLogin`. |
| `sensorfleet_ssh_server_permit_empty_passwords` | `false` | bool | sshd `PermitEmptyPasswords`. |
| `sensorfleet_ssh_server_permit_user_environment` | `false` | bool | sshd `PermitUserEnvironment`. |
| `sensorfleet_ssh_server_client_alive_interval` | `300` | int (seconds) | sshd `ClientAliveInterval`. |
| `sensorfleet_ssh_server_client_alive_count_max` | `3` | int | sshd `ClientAliveCountMax`. |
| `sensorfleet_ssh_server_login_grace_time` | `60` | int (seconds) | sshd `LoginGraceTime`. |
| `sensorfleet_ssh_server_banner` | `Unauthorized use of this system is prohibited.` | string or `null` | Content written to `/etc/ssh/banner` and referenced by sshd's `Banner` directive. `null` removes the banner file and omits the `Banner` directive entirely. |
| `sensorfleet_ssh_server_use_pam` | `true` | bool | sshd `UsePAM`. |
| `sensorfleet_ssh_server_print_motd` | `false` | bool | sshd `PrintMotd`. |
| `sensorfleet_ssh_server_challenge_response_authentication` | `false` | bool | sshd `ChallengeResponseAuthentication`/`KbdInteractiveAuthentication`. |
| `sensorfleet_ssh_server_tcp_keepalive` | `true` | bool | sshd `TCPKeepAlive`. |
| `sensorfleet_ssh_server_enable_sftp_subsystem` | `true` | bool | Whether the `Subsystem sftp ...` line is included. |
| `sensorfleet_ssh_server_allow_users` | `[]` | list of strings | sshd `AllowUsers` (empty list omits the directive, meaning no restriction). |
| `sensorfleet_ssh_server_allow_groups` | `[]` | list of strings | sshd `AllowGroups`. |
| `sensorfleet_ssh_server_deny_users` | `[]` | list of strings | sshd `DenyUsers`. |
| `sensorfleet_ssh_server_deny_groups` | `[]` | list of strings | sshd `DenyGroups`. |
| `sensorfleet_ssh_server_ciphers` | `[aes256-gcm@openssh.com, aes256-ctr]` | list of strings | sshd `Ciphers`. |
| `sensorfleet_ssh_server_macs` | `[hmac-sha2-512-etm@openssh.com]` | list of strings | sshd `MACs`. |
| `sensorfleet_ssh_server_kexalgorithms` | `[ecdh-sha2-nistp521, ecdh-sha2-nistp384, sntrup761x25519-sha512@openssh.com]` | list of strings | sshd `KexAlgorithms`. |
| `sensorfleet_ssh_server_additional_configs` | `{}` | map of directive → value | Freeform passthrough: each key/value pair is rendered as an extra `<Key> <Value>` line at the end of `sshd_config`, for directives this role doesn't expose a dedicated variable for. Takes effect after (and can override) every directive above, since `Include /etc/ssh/sshd_config.d/*.conf` at the top of the file is evaluated first by sshd but this block is appended last in the same file. |
| `sensorfleet_ssh_server_usedns` | `false` | bool | sshd `UseDNS`. |
| `sensorfleet_ssh_server_passwordauthentication` | `true` | bool | sshd `PasswordAuthentication`. |
| `sensorfleet_ssh_server_allow_tcp_forwarding` | `false` | bool | sshd `AllowTcpForwarding`. |
| `sensorfleet_ssh_server_max_sessions` | `10` | int | sshd `MaxSessions`. |
| `sensorfleet_ssh_server_max_startups` | `"10:30:60"` | string (`start:rate:full` format) | sshd `MaxStartups`. |

## sensorfleet_nginx

Installs the SSL certificate/key nginx uses for the sensor UI vhost, and related TLS options.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_nginx_sensorui_vhost_ssl_cert_path` | `null` | string (path) or `null` | Filesystem path the certificate is written to (also symlinked from `/etc/ssl/sensorfleet/ui.crt`). Must be set whenever `sensorfleet_nginx_sensorui_vhost_ssl_cert` is used. |
| `sensorfleet_nginx_sensorui_vhost_ssl_key_path` | `null` | string (path) or `null` | Filesystem path the private key is written to (also symlinked from `/etc/ssl/sensorfleet/ui.key`). |
| `sensorfleet_nginx_sensorui_vhost_ssl_cert` | `false` | string (PEM content) or `false` | Certificate content to install at the path above. `false` (the default) skips installing a certificate via Ansible — leaving certificate management to `fleetcert`'s own renewal — while any truthy string content triggers installation and disables `fleetcert webui renew` for the FM-CA cert. |
| `sensorfleet_nginx_sensorui_vhost_ssl_key` | `false` | string (PEM content) or `false` | Private key content, same on/off pattern as the certificate above. |
| `sensorfleet_nginx_sensorui_vhost_ssl_protocols` | `[TLSv1.2]` | list of strings | Rendered as nginx's `ssl_protocols` directive. |
| `sensorfleet_nginx_sensorui_vhost_ssl_ciphers` | `[ECDHE-ECDSA-AES256-GCM-SHA384, ECDHE-ECDSA-AES256-SHA384]` | list of strings | Rendered as nginx's `ssl_ciphers` directive (colon-joined). |
| `sensorfleet_nginx_sensorui_vhost_ssl_ecdh_curve` | `secp384r1` | string | Rendered as nginx's `ssl_ecdh_curve` directive. |
| `sensorfleet_nginx_sensorui_vhost_ssl_prefer_server_ciphers` | `true` | bool | Rendered as nginx's `ssl_prefer_server_ciphers on`/`off`. |
| `sensorfleet_nginx_sensorui_vhost_ssl_dhparams` | `false` | string (PEM content) or `false` | DH parameters content to install at the path below. Same on/off pattern as the certificate/key above — `false` skips installing one. |
| `sensorfleet_nginx_sensorui_vhost_ssl_dhparams_path` | `false` | string (path) or `false` | Path the DH params file is written to and referenced from (`ssl_dhparam`); a falsy value omits the `ssl_dhparam` directive entirely. |

## sensorfleet_fleetgram

Manages FM/Sensor messaging configuration and seeds an initial sensor configuration the first time a sensor has none.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_fleetgram_sensor_messaging_fm_only` | `true` | bool | Controls which sensors the rendered index config covers: when true, a sensor host only renders config for itself, while the `fleetmgmt` host renders config for every sensor in the `sensors` group; when false, every host (including sensors) renders config for the full `sensors` group. |

## sensorfleet_firewall

FM/Sensors currently use ferm as the firewall implementation but this will be changed to nftables-based one in the future. The role renders `ferm` rule fragments into `/etc/ferm/ferm.d/` (each validated with `ferm -n` before being applied). By default egress firewalling is also enabled for new installations.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_firewall_ferm_rules` | `[]` | list of strings | Raw, verbatim `ferm` rule-syntax strings, each rendered as-is into the custom-rules fragment (`90-custom-rules.conf`) — the escape hatch for rules not covered by any other variable here. |
| `sensorfleet_firewall_allow_ssh_from_anywhere` | `true` | bool | If true, opens inbound TCP access (from any source) to the sshd port(s) — port 22, `sensorfleet_globals_sshd_port` (if different), `ansible_port` (if different), and every port in `sensorfleet_globals_sshd_additional_ports`. If false, SSH access is not opened by this rule (it would need to come from `sensorfleet_firewall_ferm_rules` or another fragment instead). |
| `sensorfleet_firewall_ipv6_enable` | `false` | bool | Master IPv6 switch. If false, ferm's early rules fragment drops all IPv6 traffic outright; if true, IPv6 neighbor-discovery/MLD traffic is allowed through the dedicated IPv6 rules fragment. |
| `sensorfleet_firewall_ipv6_autoconfig` | `false` | bool | Only meaningful when IPv6 is enabled: additionally allows router-solicitation/router-advertisement ICMPv6 types needed for SLAAC. |
| `sensorfleet_firewall_allow_ingress_icmp4` | `false` | bool | Allows inbound ICMPv4 echo-request (ping) if true. |
| `sensorfleet_firewall_allow_ingress_icmp6` | `false` | bool | Allows inbound ICMPv6 echo-request if true (also requires `sensorfleet_firewall_ipv6_enable`). |
| `sensorfleet_firewall_allow_egress_icmp4` | `true` | bool | Allows outbound ICMPv4 echo-request if true. |
| `sensorfleet_firewall_allow_egress_icmp6` | `true` | bool | Allows outbound ICMPv6 echo-request if true (also requires `sensorfleet_firewall_ipv6_enable`). |
| `sensorfleet_firewall_remove_alien_dropins` | `false` | bool | If true, deletes any `*.conf` file in `/etc/ferm/ferm.d/` that isn't one of this role's own managed fragments — sweeps up drop-ins this role doesn't own. |
| `sensorfleet_firewall_enforce_egress_policy` | `true` | bool | If true, unmatched outbound traffic is logged and dropped (default-deny egress); if false, it's logged and accepted instead (default-allow egress, effectively disabling egress filtering while still logging unmatched flows). |

## sensorfleet_config

Reads the live `fleet config`, applies overrides (merge or full replace, per field), and writes it back only if something actually changed. Each configurable section (`bridges`, `homenets`, `default_retention_rules`, `event_type_retention_rules`) follows the same pattern: a value variable (`null` = leave untouched) paired with a `_replace_*` boolean that picks between two override modes:

- **Merge** (`_replace_* = false`): the given value is recursively combined (`combine(recursive=True)`) into the corresponding section of the *current* live config — existing keys not mentioned are preserved, nested maps are merged key-by-key.
- **Replace** (`_replace_* = true`): the corresponding section of the live config is replaced wholesale with the given value.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_config_bridges` | `null` | dict/list or `null` | Bridge configuration override for the `config.bridges` section. `null` makes no change. |
| `sensorfleet_config_event_type_retention_rules` | `null` | dict/list or `null` | Override for `config.event_type_retention_rules`. |
| `sensorfleet_config_default_retention_rules` | `null` | dict/list or `null` | Override for `config.default_retention_rules`. |
| `sensorfleet_config_homenets` | `null` | dict/list or `null` | Override for `config.homenets`. |
| `sensorfleet_config_replace_bridges` | `false` | bool | Merge (false) vs. replace (true) mode for `sensorfleet_config_bridges`. |
| `sensorfleet_config_replace_homenets` | `true` | bool | Merge vs. replace mode for `sensorfleet_config_homenets` — defaults to **replace**, unlike the other three sections which default to merge. |
| `sensorfleet_config_replace_default_retention_rules` | `false` | bool | Merge vs. replace mode for `sensorfleet_config_default_retention_rules`. |
| `sensorfleet_config_replace_event_type_retention_rules` | `false` | bool | Merge vs. replace mode for `sensorfleet_config_event_type_retention_rules`. |

## sensorfleet_usermgmt

Creates the initial admin account through the `fleet` CLI. Only runs on `fleetmgmt` hosts (a no-op include on sensors).

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_usermgmt_create_initial_admin_account` | `true` | bool | If false, this role does nothing at all. |
| `sensorfleet_usermgmt_default_username` | `admin` | string | Username for the initial admin account (also used as the generated-credential filename: `ui:<username>`). |
| `sensorfleet_usermgmt_default_password` | `null` | string or `null` | If set, used verbatim as the initial admin password. If `null`, a random 16-character ASCII-letter password is generated and saved to `<credential_dir>/ui:<default_username>` on the Ansible controller (so it's recoverable later) instead. |
| `sensorfleet_usermgmt_credential_dir` | `credentials` | string (path, relative to the inventory directory) | Where generated/looked-up credential files are read from and written to, resolved as `{{ inventory_dir }}/{{ this }}` on the controller (not on the target host). Created automatically if missing. |
| `sensorfleet_usermgmt_ui_force_password_change` | `true` | bool | If true, the created account is flagged to require a password change on first UI login. |

## sensorfleet_license

Installs a SensorFleet license.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_license_base64` | `null` | string (base64-encoded content) or `null` | The license file content, base64-encoded. When set, decoded and written to `/etc/sensorfleet/license.json`. `null` skips installing/changing the license file entirely (it is not removed). |

## sensorfleet_instruments

Manages instrument (e.g. netflow) configuration via `fleet config`, at both group- and host-scope, with the same merge-vs-replace pattern used by `sensorfleet_config`. Intended functionality is that user will define *_group as group-level variables in inventory and *_host as host-level variables. These will be merged to create the final configuration.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_instruments_group` | `{}` | map of instrument name → config | Instrument definitions intended to apply to every host in a group (e.g. set via `group_vars`). Merged with the host-scoped map below (host entries win on key conflicts) to produce the final `config.instruments` map, keyed `<instrument>@<inventory_hostname_short>`. |
| `sensorfleet_instruments_host` | `{}` | map of instrument name → config | Host-specific instrument definitions, merged over the group-scoped map above. |
| `sensorfleet_instruments_instrument_configs_group` | `{}` | map of instrument name → config | Group-scoped per-instrument `config` payload (the body written via `fleet config write` for each instrument named in the merged instruments map above), merged with the host-scoped map below. |
| `sensorfleet_instruments_instrument_configs_host` | `{}` | map of instrument name → config | Host-scoped per-instrument config payload, merged over the group-scoped map above (host wins on key conflicts). |
| `sensorfleet_instruments_replace_configuration` | `false` | bool | Merge (false) vs. replace (true) mode for how the top-level `config.instruments` map (built from `sensorfleet_instruments_group`/`_host`) is applied against the live fleet config — same merge/replace semantics as `sensorfleet_config`'s `_replace_*` flags. |
| `sensorfleet_instruments_replace_instrument_configuration` | `true` | bool | Merge vs. replace mode for each individual instrument's `config` payload (built from `sensorfleet_instruments_instrument_configs_group`/`_host`) — defaults to **replace**, unlike the top-level flag above which defaults to merge. |

---

## Bootstrap-only playbooks

These playbooks are designed to make an existing installation like it was installed by the installer. There might be some unknown corner cases with some cloud provider images but generally this should work. The playbooks are idempotent and can be run again if error occurs but may need override flags (see playbook specific documentation below).

Idempotency is only guaranteed on fresh installs. Running these bootstrap playbooks on existing installations might cause unintended side effects!

### sensorfleet_prepare_ubuntu

One-time bootstrap of a fresh Ubuntu install. Skips entirely (via `end_host`) if the host already has `sensorfleet-fleet-tool` and `sensorfleet-fleetcert` installed — the signal that this role's own FM/sensor bootstrap tasks already ran — unless forced.

| Variable | Default | Type | Description |
|---|---|---|---|
| `sensorfleet_prepare_ubuntu_packages` | 18 base packages (`linux-firmware`, `openssh-server`, `auditd`, `apparmor*`, `netplan.io`, `openvpn`, etc.) | list of strings | Packages installed during bootstrap and then marked "manually installed" (`apt-mark manual`) so a later `autoremove` won't remove them. |
| `sensorfleet_prepare_ubuntu_purge_packages` | `[ubuntu-minimal, ubuntu-standard, ubuntu-server, ubuntu-server-minimal, cron, rsyslog, policykit-1]` | list of strings | Packages purged (`apt purge`) during bootstrap — default Ubuntu server packages this project replaces with its own equivalents (e.g. syslog-ng instead of rsyslog). |
| `sensorfleet_prepare_ubuntu_force` | `false` | bool | If true, re-runs bootstrap even on a host that already has `sensorfleet-fleet-tool`/`sensorfleet-fleetcert` installed (normally skipped). |
| `sensorfleet_prepare_ubuntu_keep_packages_with_prefix` | `[cryptsetup]` | list of strings (regex-escaped prefixes) | Installed package names matching one of these prefixes are marked "manually installed" as well, so the bootstrap's `autoremove` step won't remove them even though they aren't in the explicit packages list above. |
| `sensorfleet_prepare_ubuntu_bootstrapping` | `true` | bool | Read by `sensorfleet_internal_certificates` (not by this role itself): while true, several nginx TLS-verification config fragments are skipped, deferring them until the actual `sensorfleet.yml` run (nginx isn't necessarily installed/configured yet during bootstrap). |