import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from .const import CONF_MMSI_LIST, CONF_TRACK_AREA, DOMAIN


class AISstreamConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the AISstream integration setup UI."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            mmsi_list = [
                m.strip()
                for m in user_input.get(CONF_MMSI_LIST, "").split(",")
                if m.strip().isdigit()
            ]
            track_area = user_input.get(CONF_TRACK_AREA, False)

            if not track_area and not mmsi_list:
                errors["base"] = "missing_targets"
            else:
                title = "AISstream Seattle" if track_area else "AISstream"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_MMSI_LIST: mmsi_list,
                        CONF_TRACK_AREA: track_area,
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
            vol.Optional(CONF_MMSI_LIST, default=""): str,
            vol.Optional(CONF_TRACK_AREA, default=True): bool,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
