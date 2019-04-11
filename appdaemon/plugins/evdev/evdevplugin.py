import asyncio
import copy
import evdev

from appdaemon.appdaemon import AppDaemon
from appdaemon.plugin_management import PluginBase


class EvdevPlugin(PluginBase):

    def __init__(self, ad: AppDaemon, name, args):
        super().__init__(ad, name, args)

        self.AD = ad
        self.stopping = False
        self.config = args
        self.name = name
        self.state = {}

        self.logger.info("evdev Plugin Initializing", "evdev")

        self.name = name

        if "namespace" in args:
            self.namespace = args["namespace"]
        else:
            self.namespace = "default"

        self.evdev_event_name = self.config.get('event_name', 'EVDEV_EVENT')
        self.evdev_devices = self.config.get('devices', [])
        self.evdev_grab = self.config.get('grab', True)
        self.evdev_device_to_future_map = {}

        self.loop = self.AD.loop  # get AD loop

        self.evdev_metadata = {
            "version": "1.0",
            "event_name": self.evdev_event_name,
            "topics": self.evdev_devices,
            "grab": self.evdev_grab
        }

        self.logger.info("evdev Plugin initialization complete")

    def stop(self):
        self.logger.debug("stop() called for %s", self.name)
        self.stopping = True
        self.logger.info("Stopping EVDEV Plugin")
        if self.evdev_grab:
            for device in self.evdev_devices:
                device.ungrab()

    async def call_plugin_service(self, namespace, domain, service, kwargs):
        if 'device' in kwargs:
            try:
                device = kwargs['device']

                if service == 'subscribe':
                    self.logger.debug("Subscribe to device: %s", device)
                    result = self.subscribe(device)
                    self.logger.debug("Subscribe to device %s Successful", device)
                elif service == 'unsubscribe':
                    self.logger.debug("Unsubscribe from device: %s", device)
                    self.unsubscribe(device)
                    result = None
                    self.logger.debug("Unsubscribe from device %s Successful", device)
                else:
                    self.logger.warning("Wrong Service Call %s for EVDEV", service)
                    result = 'ERR'

            except Exception as e:
                config = self.config
                if config['type'] == 'evdev':
                    self.logger.debug('Got the following Error %s, when trying to retrieve Evdev Plugin', e)
                    return str(e)
                else:
                    self.logger.critical(
                        'Wrong Namespace %s selected for EVDEV Service. Please use proper namespace before trying again'
                        ,namespace)
                    return 'ERR'
        else:
            self.logger.warning('Device not provided for Service Call {!r}.'.format(service))
            raise ValueError("Device not provided, please provide Topic for Service Call")

        return result

    def subscribe(self, device):
        if device not in self.evdev_devices:
            evdev_device = evdev.InputDevice(device)
            my_future = asyncio.ensure_future(self.handle_device(evdev_device))
            self.evdev_devices.append(device)
            self.evdev_device_to_future_map[device] = {"future": my_future, "evdev_device": evdev_device}
            return my_future
        else:
            self.logger.warning("Already subscribed to device %s".format(device))
            return None

    def unsubscribe(self, device):
        if device in self.evdev_devices:
            self.evdev_devices.remove(device)
            future_and_evdev = self.evdev_device_to_future_map.pop(device, None)
            if future_and_evdev is not None:
                future_and_evdev['my_future'].cancel()
                if self.evdev_grab:
                    future_and_evdev['evdev_device'].ungrab()
            else:
                self.logger.warning("Someone else unsubscribed before we got the chance for device %s".format(device))
        else:
            self.logger.warning("Not subscribed to device %s".format(device))

    async def handle_device(self, device):
        try:
            async for event in device.async_read_loop():
                self.logger.info(device.path, evdev.categorize(event), sep=': ')
                data = {'event_type': self.evdev_event_name, 'data': {'device': device, 'payload': msg.payload.decode()}}
                self.loop.create_task(self.send_ad_event(data))
        except asyncio.CancelledError:
            print('Cancelled reading for device'.format(device))

    async def send_ad_event(self, data):
        await self.AD.events.process_event(self.namespace, data)

    async def get_complete_state(self):
        self.logger.debug("*** Sending Complete State: {} ***".format(self.state))
        return copy.deepcopy(self.state)

    async def get_metadata(self):
        return self.evdev_metadata

    def utility(self):
        pass
        # self.logger.debug("*** Utility ***".format(self.state))

    #
    # Handle state updates
    #
    async def get_updates(self):
        await self.AD.plugins.notify_plugin_started(self.name, self.namespace, self.get_metadata(), self.get_complete_state(), True)
        while not self.stopping:
            ret = None
            if self.current_event >= len(self.config["sequence"]["events"]) and ("loop" in self.config["sequence"] and self.config["loop"] == 0 or "loop" not in self.config["sequence"]):
                while not self.stopping:
                    await asyncio.sleep(1)
                return None
            else:
                event = self.config["sequence"]["events"][self.current_event]
                await asyncio.sleep(event["offset"])
                if "state" in event:
                    entity = event["state"]["entity"]
                    old_state = self.state[entity]
                    new_state = event["state"]["newstate"]
                    self.state[entity] = new_state
                    ret = \
                        {
                            "event_type": "state_changed",
                            "data":
                                {
                                    "entity_id": entity,
                                    "new_state": new_state,
                                    "old_state": old_state
                                }
                        }
                    self.logger.debug("*** State Update: %s ***", ret)
                    await self.AD.state.process_event(self.namespace, copy.deepcopy(ret))
                elif "event" in event:
                    ret = \
                        {
                            "event_type": event["event"]["event_type"],
                            "data": event["event"]["data"],
                        }
                    self.logger.debug("*** Event: %s ***", ret)
                    await self.AD.state.process_event(self.namespace, copy.deepcopy(ret))

                elif "disconnect" in event:
                    self.logger.debug("*** Disconnected ***")
                    self.AD.plugins.notify_plugin_stopped(self.namespace)

                elif "connect" in event:
                    self.logger.debug("*** Connected ***")
                    await self.AD.plugins.notify_plugin_started(self.namespace)

                self.current_event += 1
                if self.current_event >= len(self.config["sequence"]["events"]) and "loop" in self.config["sequence"] and self.config["sequence"]["loop"] == 1:
                    self.current_event = 0

    def set_plugin_state(self, entity, state, **kwargs):
        self.logger.debug("*** Setting State: %s = %s ***", entity, state)
        self.state[entity] = state

    def get_namespace(self):
        return self.namespace

