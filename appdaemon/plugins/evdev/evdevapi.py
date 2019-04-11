import appdaemon.adbase as adbase
import appdaemon.adapi as adapi
from appdaemon.appdaemon import AppDaemon
import appdaemon.utils as utils


class Evdev(adbase.ADBase, adapi.ADAPI):

    """
    A list of API calls and information specific to the EVDEV plugin.

    App Creation
    ------------

    To create apps based on just the EVDEV API, use some code like the following:

    .. code:: python

        import evdevapi as evdev

        class MyApp(evdev.Evdev):

            def initialize(self):

    Making Calls to EVDEV
    ---------------------

    AD API's ``call_service()`` is used to carry out service calls from within an AppDaemon app. This allows the app
    to carry out one of the following services:

      - ``Publish``
      - ``Subscribe``
      - ``Unsubscribe``

    By simply specifying within the function what is to be done. It uses configuration specified in the plugin
    configuration which simplifies the call within the app significantly.

    Examples
    ^^^^^^^^

    .. code:: python

        # if wanting to subscribe to a device
        self.call_service("subscribe", device = "/dev/inputX")
        # if wanting to unsubscribe from a device in a different namespace
        self.call_service("unsubscribe", device= "/dev/inputX", namespace = "mqtt2")

    The EVDEV API also provides 2 convenience functions to make calling of specific functions easier an more readable.
    These are documented in the following section.
    """

    def __init__(self, ad: AppDaemon, name, logging, args, config, app_config, global_vars,):
        """
        Constructor for the app.

        :param ad: appdaemon object
        :param name: name of the app
        :param logging: reference to logging object
        :param args: app arguments
        :param config: AppDaemon config
        :param app_config: config for all apps
        :param global_vars: reference to global variables dict
        """
        # Call Super Classes
        adbase.ADBase.__init__(self, ad, name, logging, args, config, app_config, global_vars)
        adapi.ADAPI.__init__(self, ad, name, logging, args, config, app_config, global_vars)


    #
    # Override listen_event()
    #

    def listen_event(self, cb, event=None, **kwargs):

        """
        This is the primary way of listening for changes within the EVDEV plugin.

        Unlike other plugins, EVDEV does not keep state. All EVDEV messages will have an event which is set to ``MQTT_MESSAGE`` by default. This can be changed to whatever that is required in the plugin configuration.

        :param cb: Function to be invoked when the requested state change occurs. It must conform to the standard Event Callback format documented `Here <APPGUIDE.html#about-event-callbacks>`__.
        :param event: Name of the event to subscribe to. Can be the declared ``event_name`` parameter as specified in the plugin configuration. If no event is specified, ``listen_event()`` will subscribe to all MQTT events within the app's functional namespace.
        :param \*\*kwargs: Additional keyword arguments:

            **namespace** (optional):  Namespace to use for the call - see the section on namespaces for a detailed description. In most cases it is safe to ignore this parameter. The value ``global`` for namespace has special significance, and means that the callback will lsiten to state updates from any plugin.

        :return: A handle that can be used to cancel the callback.
        """

        return super(Evdev, self).listen_event(cb, event, **kwargs)

    def evdev_subscribe(self, topic, **kwargs):

        """
        A helper function used for subscribing to a device, from within an AppDaemon app.

        This allows the apps to now access events from that device, in realtime.
        So outside the initial configuration at plugin config, this allows access to other devices while the apps runs.
        It should be noted that if Appdaemon was to reload, the devices subscribed via this function will not be
        available by default. Those declared at the plugin config will always be available. It uses configuration
        specified in the plugin configuration which simplifies the call within the app significantly.

        :param device: The device to be subscribed to e.g. ``/dev/inputX``
        """

        kwargs['device'] = topic
        service = 'evdev/subscribe'
        result = self.call_service(service, **kwargs)
        return result

    def evdev_unsubscribe(self, topic, **kwargs):

        """
        A helper function used for unsubscribing from a device, from within an AppDaemon app.

        This denies the apps access to events from that device, in realtime. It is possible to unsubscribe from devices,
        even if they were part of the devices in the plugin config; It should also be noted that if Appdaemon was to
        reload, the devices unsubscribed via this function will be available if they were configured with the plugin by
        default. It uses configuration specified in the plugin configuration which simplifies the call within the app
        significantly.

        :param device: The device to be unsubscribed from e.g. ``/dev/inputX``
        """

        kwargs['device'] = topic
        service = 'evdev/unsubscribe'
        result = self.call_service(service, **kwargs)
        return result
