from ironman.hardware import HardwareManager, HardwareMap, HardwareNode
manager = HardwareManager()
manager.add(HardwareMap(file('xadc.yml').read(), 'xadc'))

from ironman.communicator import Jarvis, ComplexIO
j = Jarvis()
j.set_hardware_manager(manager)

@j.register('xadc')
class XADCController(ComplexIO):
    __base__ = "/sys/devices/soc0/amba/f8007100.adc/iio:device0/"
    __f__ = {
                0:   __base__+"in_temp0_offset",
                1:   __base__+"in_temp0_raw",
                2:   __base__+"in_temp0_scale",
                17:  __base__+"in_voltage0_vccint_raw",
                18:  __base__+"in_voltage0_vccint_scale",
                33:  __base__+"in_voltage1_vccaux_raw",
                34:  __base__+"in_voltage1_vccaux_scale",
                49:  __base__+"in_voltage2_vccbram_raw",
                50:  __base__+"in_voltage2_vccbram_scale",
                65:  __base__+"in_voltage3_vccpint_raw",
                66:  __base__+"in_voltage3_vccpint_scale",
                81:  __base__+"in_voltage4_vccpaux_raw",
                82:  __base__+"in_voltage4_vccpaux_scale",
                97:  __base__+"in_voltage5_vccoddr_raw",
                98:  __base__+"in_voltage5_vccoddr_scale",
                113: __base__+"in_voltage6_vrefp_raw",
                114: __base__+"in_voltage6_vrefp_scale",
                129: __base__+"in_voltage7_vrefn_raw",
                130: __base__+"in_voltage7_vrefn_scale"
            }

from ironman.constructs.ipbus import PacketHeaderStruct, ControlHeaderStruct
def buildResponsePacket(packet):
    data = ''
    data += PacketHeaderStruct.build(packet.struct.header)
    for transaction, response in zip(packet.struct.data, packet.response):
        data += ControlHeaderStruct.build(transaction)
        data += response.encode("hex").decode("hex")
    return data


from ironman.history import History
h = History()

from ironman.server import ServerFactory
from ironman.packet import IPBusPacket
from twisted.internet import reactor
from twisted.internet.defer import Deferred

def deferredGenerator():
    return Deferred().addCallback(IPBusPacket).addCallback(j).addCallback(buildResponsePacket).addCallback(h.record)

reactor.listenUDP(8888, ServerFactory('udp', deferredGenerator))

'''set up a web server from top level: http://imgur.com/jCQlfrm'''
# Site, an IProtocolFactory which glues a listening server port (IListeningPort) to the HTTPChannel implementation
from twisted.web.server import Site
# File, an IResource which glues the HTTP protocol implementation to the filesystem
from twisted.web.static import File
reactor.listenTCP(8000, Site(File("/")))

'''set up a mirror web server for IPBus requests'''
from twisted.web.resource import Resource
# deferred responses
from twisted.web.server import NOT_DONE_YET
# return json
import json
class HTTPIPBusRoot(Resource):
    # has children
    isLeaf = False

class HTTPIPBus(Resource):
    # no children
    isLeaf = True
    def render_GET(self, request):
        request.responseHeaders.addRawHeader(b"content-type", b"application/json")
        # request.postpath will contain what we need
        if len(request.postpath) != 3:
            return json.dumps({
                "success": False,
                "data": None,
                "error": "Incorrect number of URL segments",
                "traceback": None
            })

        def write(result):
            request.write(json.dumps({
                "success": True,
                "data": result,
                "error": None,
                "traceback": None
            }))
            request.finish()

        def error(result):
            request.write(json.dumps({
                "success": False,
                "data": None,
                "error": "An unknown error has occurred with the application. Message: {0}".format(result.getErrorMessage()),
                "traceback": result.getBriefTraceback()
            }))
            request.finish()

        d = deferredGenerator()
        d.addCallbacks(write, error)
        d.callback('test')
        return NOT_DONE_YET

http_ipbus_root = HTTPIPBusRoot()
http_ipbus_root.putChild('read', HTTPIPBus())
reactor.listenTCP(7777, Site(http_ipbus_root))

reactor.run()
