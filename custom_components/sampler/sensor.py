"""Sensor platform for sampler integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import RestoreSensor, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_PERIOD

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize sampler config entry."""
    registry = er.async_get(hass)
    # Validate + resolve entity registry id to entity_id
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    name = config_entry.title
    unique_id = config_entry.entry_id
    period = config_entry.options[CONF_PERIOD]
    async_add_entities([SamplerSensorEntity(unique_id, name, entity_id, period)])


class SamplerSensorEntity(RestoreSensor, SensorEntity):
    """sampler Sensor."""

    def __init__(
        self, unique_id: str, name: str, sensor_source_id: str, period: int
    ) -> None:
        """Initialize sampler Sensor."""
        super().__init__()
        self._sensor_source_id = sensor_source_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._unit_of_measurement = None
        self._period = period
        self._state: str | None = None
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) is not None and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._state = last_state.state
            self._unit_of_measurement = last_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )
            self._attr_device_class = last_state.attributes.get(ATTR_DEVICE_CLASS)

        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._sample_source_entity, timedelta(seconds=self._period)
            ),
        )

    @callback
    def _sample_source_entity(self, now: datetime) -> None:
        """Handle the sensor state changes."""
        self._attr_extra_state_attributes = {
            "last_sample": now.isoformat(),
        }

        if (
            source_state := self.hass.states.get(self._sensor_source_id)
        ) is None or source_state.state in [STATE_UNAVAILABLE]:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        self._state = source_state.state if source_state.state != STATE_UNKNOWN else None
        self._unit_of_measurement = source_state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )
        self._attr_device_class = source_state.attributes.get(ATTR_DEVICE_CLASS)
        self.async_write_ha_state()
        _LOGGER.debug("Sensor %s changed to %s", self._attr_name, self._state)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement
