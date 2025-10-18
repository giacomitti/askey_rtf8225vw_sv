"""Configuração SSH com suporte a algoritmos legacy."""

SSH_OPTIONS = {
    'disabled_algorithms': {
        'pubkeys': [],
    },
    'host_key_policy': 'auto_add'
}