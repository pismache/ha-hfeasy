"""Tests de l'intégration HFeasy contre une prise simulée (adresses fictives)."""

from datetime import timedelta

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.hfeasy.const import CONF_SCAN_INTERVAL, DOMAIN

HOST = "192.0.2.10"  # plage réservée à la documentation
PORT = 8080
URL = f"http://{HOST}:{PORT}/state"
ENTITY = "switch.prise_test"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def state(on: bool) -> dict:
    return {"set": "none", "relay_status": "1" if on else "0"}


def make_entry(hass: HomeAssistant, **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Prise test",
        unique_id=f"{HOST}:{PORT}",
        data={CONF_HOST: HOST, CONF_PORT: PORT, **data},
    )
    entry.add_to_hass(hass)
    return entry


async def setup(hass, aioclient_mock, on=False, **data) -> MockConfigEntry:
    aioclient_mock.get(URL, json=state(on))
    entry = make_entry(hass, **data)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


# --- Ajout par l'interface -------------------------------------------------


async def test_user_flow(hass, aioclient_mock):
    aioclient_mock.get(URL, json=state(True))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: f" {HOST} ", CONF_PORT: PORT, CONF_NAME: "Prise test"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Prise test"
    assert result["data"][CONF_HOST] == HOST
    assert CONF_NAME not in result["data"]
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    assert hass.states.get(ENTITY).state == STATE_ON


@pytest.mark.parametrize(
    ("mock", "error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 500}, "cannot_connect"),
        ({"text": "<html>pas une prise</html>"}, "cannot_connect"),
        ({"json": {"autre": "chose"}}, "cannot_connect"),
        ({"exc": TimeoutError()}, "cannot_connect"),
    ],
)
async def test_user_flow_errors(hass, aioclient_mock, mock, error):
    aioclient_mock.get(URL, **mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: "Prise test"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_user_flow_already_configured(hass, aioclient_mock):
    make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: "x"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_basic_auth_is_sent(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, **{CONF_USERNAME: "admin", CONF_PASSWORD: "secret"})
    auth = entry.runtime_data.api._auth
    assert (auth.login, auth.password) == ("admin", "secret")
    assert hass.states.get(ENTITY).state == STATE_OFF


async def test_no_auth_when_username_empty(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, **{CONF_USERNAME: "", CONF_PASSWORD: ""})
    assert entry.runtime_data.api._auth is None


# --- Interrupteur -----------------------------------------------------------


async def test_switch_on_off(hass, aioclient_mock):
    await setup(hass, aioclient_mock, on=False)
    assert hass.states.get(ENTITY).state == STATE_OFF
    assert hass.states.get(ENTITY).attributes["device_class"] == "outlet"

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, params={"sw": "1"}, json=state(True))
    await hass.services.async_call("switch", "turn_on", {"entity_id": ENTITY}, blocking=True)
    assert hass.states.get(ENTITY).state == STATE_ON
    assert str(aioclient_mock.mock_calls[-1][1]).endswith("/state?sw=1")

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, params={"sw": "0"}, json=state(False))
    await hass.services.async_call("switch", "turn_off", {"entity_id": ENTITY}, blocking=True)
    assert hass.states.get(ENTITY).state == STATE_OFF
    assert str(aioclient_mock.mock_calls[-1][1]).endswith("/state?sw=0")


async def test_switch_command_fails(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, params={"sw": "1"}, exc=TimeoutError())
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": ENTITY}, blocking=True
        )


async def test_unavailable_then_back(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock, on=True)
    assert hass.states.get(ENTITY).state == STATE_ON

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=TimeoutError())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=state(False))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=62))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_OFF
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_retry_when_offline(hass, aioclient_mock):
    aioclient_mock.get(URL, exc=TimeoutError())
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


# --- Identifiants, reconfiguration, options -------------------------------


async def test_auth_failure_starts_reauth(hass, aioclient_mock):
    aioclient_mock.get(URL, status=401)
    entry = make_entry(hass, **{CONF_USERNAME: "admin", CONF_PASSWORD: "ancien"})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=state(True))
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "nouveau"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "nouveau"
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfigure_new_ip_keeps_entity(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    new_host = "192.0.2.20"
    aioclient_mock.get(f"http://{new_host}:{PORT}/state", json=state(True))

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert CONF_NAME not in {str(k) for k in result["data_schema"].schema}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host, CONF_PORT: PORT}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == new_host
    assert entry.unique_id == f"{new_host}:{PORT}"
    # même entité, pas de doublon
    assert hass.states.get(ENTITY).state == STATE_ON
    assert len(hass.states.async_entity_ids("switch")) == 1


async def test_reconfigure_to_other_configured_plug(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    MockConfigEntry(
        domain=DOMAIN, title="Autre", unique_id=f"192.0.2.30:{PORT}",
        data={CONF_HOST: "192.0.2.30", CONF_PORT: PORT},
    ).add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.30", CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_scan_interval(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 10}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 10
    assert entry.runtime_data.update_interval == timedelta(seconds=10)


async def test_unload(hass, aioclient_mock):
    entry = await setup(hass, aioclient_mock)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
