"""Sensor platform para Askey RTF8225VW-SV."""
import paramiko
import re
import logging
import time
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DOMAIN = "askey_rtf8225vw_sv"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configura os sensores a partir de uma config entry."""
    _LOGGER.info("Configurando sensores Askey RTF8225VW-SV")
    
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    # Usa o scan_interval das opções ou da configuração inicial
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, 300)
    )
    
    coordinator = TransceiverDataCoordinator(
        hass, host, username, password, scan_interval, entry.entry_id
    )
    
    await coordinator.async_config_entry_first_refresh()
    
    sensors = [
        TransceiverSensor(coordinator, entry, "tx_power", "Tx Power", "dBm", "mdi:upload-network"),
        TransceiverSensor(coordinator, entry, "rx_power", "Rx Power", "dBm", "mdi:download-network"),
        TransceiverSensor(coordinator, entry, "uptime", "Uptime", "s", "mdi:clock-outline", SensorDeviceClass.DURATION),
        TransceiverUptimeHumanSensor(coordinator, entry),
        ONUStateSensor(coordinator, entry),
    ]
    
    async_add_entities(sensors, True)
    _LOGGER.info("Sensores adicionados com sucesso")


class TransceiverDataCoordinator(DataUpdateCoordinator):
    """Coordenador para atualizar dados do transceiver."""
    
    def __init__(self, hass, host, username, password, scan_interval, entry_id):
        """Inicializa o coordenador."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.username = username
        self.password = password
        self.entry_id = entry_id
    
    async def _async_update_data(self):
        """Busca dados via SSH."""
        _LOGGER.debug(f"Atualizando dados para {self.host}")
        return await self.hass.async_add_executor_job(self._fetch_data)
    
    def _fetch_data(self):
        """Executa comando SSH e extrai dados usando shell interativo."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # Conecta via SSH
            ssh.connect(
                hostname=self.host,
                username=self.username,
                password=self.password,
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            
            _LOGGER.debug("Conexão SSH estabelecida")
            
            # Usa invoke_shell para simular sessão interativa
            channel = ssh.invoke_shell()
            time.sleep(1)
            
            # Limpa buffer inicial
            if channel.recv_ready():
                channel.recv(4096)
            
            # Comando 1: diag transceiver show
            channel.send("diag transceiver show\n")
            time.sleep(2)
            
            output = ""
            attempts = 0
            max_attempts = 10
            
            while attempts < max_attempts:
                if channel.recv_ready():
                    chunk = channel.recv(4096).decode('utf-8', errors='ignore')
                    output += chunk
                    time.sleep(0.5)
                else:
                    if output:
                        time.sleep(0.5)
                        attempts += 1
                    else:
                        time.sleep(0.5)
                        attempts += 1
            
            # Comando 2: sys_info show uptime
            channel.send("sys_info show uptime\n")
            time.sleep(2)
            
            uptime_output = ""
            attempts = 0
            
            while attempts < max_attempts:
                if channel.recv_ready():
                    chunk = channel.recv(4096).decode('utf-8', errors='ignore')
                    uptime_output += chunk
                    time.sleep(0.5)
                else:
                    if uptime_output:
                        time.sleep(0.5)
                        attempts += 1
                    else:
                        time.sleep(0.5)
                        attempts += 1
            
            # Comando 3: onu dev_info show onu_state
            channel.send("onu dev_info show onu_state\n")
            time.sleep(2)
            
            onu_output = ""
            attempts = 0
            
            while attempts < max_attempts:
                if channel.recv_ready():
                    chunk = channel.recv(4096).decode('utf-8', errors='ignore')
                    onu_output += chunk
                    time.sleep(0.5)
                else:
                    if onu_output:
                        time.sleep(0.5)
                        attempts += 1
                    else:
                        time.sleep(0.5)
                        attempts += 1
            
            channel.send("exit\n")
            time.sleep(1)
            channel.close()
            
            # Extrai valores
            tx_power = None
            rx_power = None
            uptime = None
            onu_state = None
            
            # Tx Power
            tx_match = re.search(r'Tx\s+power\s*=\s*([-+]?\d+\.?\d*)\s*dBm', output, re.IGNORECASE)
            if tx_match:
                tx_power = float(tx_match.group(1))
            else:
                tx_match_alt = re.search(r'Tx\s*power\s*=\s*([-+]?\d+\.?\d*)', output, re.IGNORECASE)
                if tx_match_alt:
                    tx_power = float(tx_match_alt.group(1))
            
            # Rx Power
            rx_match = re.search(r'Rx\s+power\s*=\s*([-+]?\d+\.?\d*)\s*dBm', output, re.IGNORECASE)
            if rx_match:
                rx_power = float(rx_match.group(1))
            else:
                rx_match_alt = re.search(r'Rx\s*power\s*=\s*([-+]?\d+\.?\d*)', output, re.IGNORECASE)
                if rx_match_alt:
                    rx_power = float(rx_match_alt.group(1))
            
            # Uptime
            uptime_match = re.search(r'Uptime\s*=\s*(\d+)\s*seconds', uptime_output, re.IGNORECASE)
            if uptime_match:
                uptime = int(uptime_match.group(1))
            
            # ONU State - Regex ajustado para sem espaço antes de 'ONU State'
            onu_match = re.search(r'ONU State:\s*([A-Z]\d+)', onu_output, re.IGNORECASE)
            if onu_match:
                onu_state = onu_match.group(1)
            
            _LOGGER.debug(f"Valores extraídos - Tx: {tx_power}, Rx: {rx_power}, Uptime: {uptime}, ONU State: {onu_state}")
            _LOGGER.debug(f"Saída ONU: {onu_output[:500]}...")  # Log parcial para debug
            
            return {
                "tx_power": tx_power,
                "rx_power": rx_power,
                "uptime": uptime,
                "onu_state": onu_state
            }
            
        except Exception as e:
            _LOGGER.error(f"Erro ao buscar dados via SSH: {e}")
            return {
                "tx_power": None,
                "rx_power": None,
                "uptime": None,
                "onu_state": None
            }
        finally:
            try:
                ssh.close()
            except:
                pass


class TransceiverSensor(CoordinatorEntity, SensorEntity):
    """Sensor individual para cada métrica."""
    
    def __init__(self, coordinator, entry, sensor_type, name, unit, icon, device_class=None):
        """Inicializa o sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_name = f"Askey RTF8225VW-SV {name}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{sensor_type}"
        self._attr_has_entity_name = False
        
        # Informações do dispositivo
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Askey RTF8225VW-SV ({entry.data[CONF_HOST]})",
            "manufacturer": "Askey",
            "model": "RTF8225VW-SV",
            "sw_version": "1.0",
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }
    
    @property
    def native_value(self):
        """Retorna o valor do sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._sensor_type)
        return None
    
    @property
    def available(self):
        """Retorna se o sensor está disponível."""
        return self.coordinator.last_update_success and self.native_value is not None


class TransceiverUptimeHumanSensor(CoordinatorEntity, SensorEntity):
    """Sensor para uptime legível por humanos."""
    
    def __init__(self, coordinator, entry):
        """Inicializa o sensor."""
        super().__init__(coordinator)
        self._attr_name = "Askey RTF8225VW-SV Uptime Human"
        self._attr_icon = "mdi:clock-outline"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_uptime_human"
        self._attr_has_entity_name = False
        # Remove device_class para permitir valores string
        
        # Informações do dispositivo (mesmas dos outros)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Askey RTF8225VW-SV ({entry.data[CONF_HOST]})",
            "manufacturer": "Askey",
            "model": "RTF8225VW-SV",
            "sw_version": "1.0",
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }
    
    @property
    def native_value(self):
        """Retorna o valor formatado do sensor."""
        uptime_seconds = self.coordinator.data.get("uptime") if self.coordinator.data else None
        if uptime_seconds is not None:
            return self._format_uptime(uptime_seconds)
        return None
    
    def _format_uptime(self, seconds: int) -> str:
        """Formata segundos em string legível (ex.: '1d 2h 30m')."""
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        seconds_rem = seconds % 60
        if minutes < 60:
            return f"{minutes}m {seconds_rem}s" if seconds_rem > 0 else f"{minutes}m"
        hours = minutes // 60
        minutes_rem = minutes % 60
        if hours < 24:
            return f"{hours}h {minutes_rem}m" if minutes_rem > 0 else f"{hours}h"
        days = hours // 24
        hours_rem = hours % 24
        return f"{days}d {hours_rem}h" if hours_rem > 0 else f"{days}d"
    
    @property
    def available(self):
        """Retorna se o sensor está disponível."""
        return self.coordinator.last_update_success and self.native_value is not None


class ONUStateSensor(CoordinatorEntity, SensorEntity):
    """Sensor para estado da ONU com descrição."""
    
    def __init__(self, coordinator, entry):
        """Inicializa o sensor."""
        super().__init__(coordinator)
        self._attr_name = "Askey RTF8225VW-SV ONU State"
        self._attr_icon = "mdi:signal"
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_onu_state"
        self._attr_has_entity_name = False
        
        # Informações do dispositivo (mesmas dos outros)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Askey RTF8225VW-SV ({entry.data[CONF_HOST]})",
            "manufacturer": "Askey",
            "model": "RTF8225VW-SV",
            "sw_version": "1.0",
            "configuration_url": f"http://{entry.data[CONF_HOST]}",
        }
    
    @property
    def native_value(self):
        """Retorna o valor formatado do sensor (código - descrição)."""
        state_code = self.coordinator.data.get("onu_state") if self.coordinator.data else None
        if state_code:
            description = self._get_description(state_code)
            return f"{state_code} - {description}"
        return None
    
    def _get_description(self, code: str) -> str:
        """Mapeia o código do estado para descrição."""
        mapping = {
            'O1': 'Initial',
            'O2': 'Standby',
            'O3': 'Serial Number',
            'O4': 'Ranging',
            'O5': 'Operational',
            'O6': 'Pop-up',
            'O7': 'Emergency Stop',
        }
        return mapping.get(code, 'Unknown')
    
    @property
    def available(self):
        """Retorna se o sensor está disponível."""
        return self.coordinator.last_update_success and self.coordinator.data.get("onu_state") is not None