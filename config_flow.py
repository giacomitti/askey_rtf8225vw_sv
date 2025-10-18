"""Config flow para Askey RTF8225VW-SV."""
import logging
import voluptuous as vol
import paramiko

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DOMAIN = "askey_rtf8225vw_sv"

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="192.168.15.1"): str,
    vol.Required(CONF_USERNAME, default="support"): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=300): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
})


class AskeyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow para Askey RTF8225VW-SV."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Manipula o passo inicial da configuração."""
        errors = {}

        if user_input is not None:
            # Valida a conexão SSH
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            
            # Testa a conexão
            try:
                await self.hass.async_add_executor_job(
                    self._test_connection, host, username, password
                )
                
                # Cria a entrada com título personalizado
                title = f"Askey RTF8225VW-SV ({host})"
                
                # Verifica se já existe uma entrada com o mesmo host
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=title, data=user_input)
                
            except paramiko.AuthenticationException:
                errors["base"] = "invalid_auth"
            except paramiko.SSHException as e:
                _LOGGER.error(f"Erro SSH: {e}")
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.error(f"Erro inesperado: {e}")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "host": "Endereço IP do dispositivo",
                "username": "Nome de usuário SSH",
                "password": "Senha SSH",
                "scan_interval": "Intervalo de atualização em segundos (30-3600)",
            }
        )

    def _test_connection(self, host, username, password):
        """Testa a conexão SSH."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False
            )
            _LOGGER.info(f"Conexão SSH testada com sucesso para {host}")
            return True
        finally:
            ssh.close()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Retorna o options flow."""
        return AskeyOptionsFlow(config_entry)


class AskeyOptionsFlow(config_entries.OptionsFlow):
    """Options flow para Askey RTF8225VW-SV."""

    async def async_step_init(self, user_input=None):
        """Manipula as opções."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.options.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(CONF_SCAN_INTERVAL, 300)
                    )
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
            })
        )