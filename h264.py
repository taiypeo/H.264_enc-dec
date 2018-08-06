import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import math

MAX_BUFFERS = 100

class VideoFrame:
    def __init__(self, width, height, data=None):
        self.width = width
        self.height = height

        if data is None:
            self.data = b'\x00' * math.ceil(width * height * 12 / 8)
        else:
            self.data = data

class H264_Encoder:
    @staticmethod
    def __create_srccaps(width, height):
        CAPS_STR = 'video/x-raw,format=I420,width={},height={},framerate=0/1'
        return Gst.Caps.from_string(CAPS_STR.format(width, height))

    def __create_pipeline(self):
        self.pipeline = Gst.Pipeline.new()
        # appsrc -> rawvideoparse -> videoconvert -> x264enc -> rtph264pay -> appsink

        self.appsrc = Gst.ElementFactory.make('appsrc')
        self.appsrc.set_property('caps', self.__create_srccaps(0, 0))

        def feed_appsrc(bus, msg):
            if len(self.frames) == 0:
                self.appsrc.emit('end-of-stream')
            else:
                buf = Gst.Buffer.new_wrapped(self.frames[0].data)
                self.appsrc.emit('push-buffer', buf)
                del(self.frames[0])

        self.appsrc.connect('need-data', feed_appsrc)

        self.videoparse = Gst.ElementFactory.make('rawvideoparse')
        self.videoparse.set_property('width', 0)
        self.videoparse.set_property('height', 0)
        self.videoparse.set_property('framerate', Gst.Fraction(0))

        videoconvert = Gst.ElementFactory.make('videoconvert')
        x264_encoder = Gst.ElementFactory.make('x264enc')
        rtp_payloader = Gst.ElementFactory.make('rtph264pay')

        self.appsink = Gst.ElementFactory.make('appsink')
        rtpcaps = Gst.Caps.from_string(
            'application/x-rtp,payload=96,media=video,encoding-name=H264,clock-rate=90000'
        )
        self.appsink.set_property('caps', rtpcaps)
        self.appsink.set_property('drop', True) # should we drop??
        self.appsink.set_property('max-buffers', MAX_BUFFERS)
        self.appsink.set_property('emit-signals', True)

        def get_appsink_data(sink):
            sample = sink.emit('pull-sample')
            if not sample:
                return
            buf = sample.get_buffer()
            status, info = buf.map(Gst.MapFlags.READ)
            if not status:
                raise Exception('H264_Encoder error: failed to map buffer data to GstMapInfo')
            self.payloads.append(info.data)
            buf.unmap(info)

            return Gst.FlowReturn.OK

        self.appsink.connect('new-sample', get_appsink_data)

        self.pipeline.add(self.appsrc)
        self.pipeline.add(self.videoparse)
        self.pipeline.add(videoconvert)
        self.pipeline.add(x264_encoder)
        self.pipeline.add(rtp_payloader)
        self.pipeline.add(self.appsink)

        self.appsrc.link(self.videoparse)
        self.videoparse.link(videoconvert)
        videoconvert.link(x264_encoder)
        x264_encoder.link(rtp_payloader)
        rtp_payloader.link(self.appsink)

    def update_parameters(self, width, height):
        self.appsrc.set_property('caps', self.__create_srccaps(width, height))

        self.videoparse.set_property('width', width)
        self.videoparse.set_property('height', height)

    def change_state(self, state):
        state = self.pipeline.set_state(state)
        if state == Gst.StateChangeReturn.FAILURE:
            raise Exception('H264_Encoder error: failed to change pipeline\'s state to', str(state))

    def __init__(self):
        self.frames = []
        self.payloads = []

        self.__create_pipeline()

        self.change_state(Gst.State.READY)

    def __del__(self):
        self.pipeline.set_state(Gst.State.NULL)

    '''
    Encodes raw YUV420 video frames with H.264 and packages the result in RTP payloads

    :param frames: list of VideoFrame objects with *same* width and height
    :returns: list of binary representations of RTP payloads
    '''
    def encode(self, frames):
        if len(frames) == 0:
            raise Exception('H264_Encoder error: \'frames\' length should be greater than 0')

        self.frames = frames
        self.update_parameters(frames[0].width, frames[0].height)
        self.change_state(Gst.State.PLAYING)

        msg = self.pipeline.get_bus().timed_pop_filtered(Gst.CLOCK_TIME_NONE,
            Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, _ = msg.parse_error()
                raise Exception('H264_Encoder error: pipeline failure: ' + err.message)
            elif msg.type != Gst.MessageType.EOS:
                raise Exception('H264_Encoder error: pipeline failure: unknown error')

        self.change_state(Gst.State.READY)

        current_payloads = self.payloads

        self.frames = []
        self.payloads = []

        return current_payloads

##############################################################################

class H264_Decoder:
    def __create_pipeline(self):
        self.pipeline = Gst.Pipeline.new()
        # appsrc -> rtph264depay -> h264parse -> avdec_h264 -> videoconvert -> appsink

        self.appsrc = Gst.ElementFactory.make('appsrc')
        self.appsrc.set_property('format', Gst.Format.TIME)
        rtpcaps = Gst.Caps.from_string(
            'application/x-rtp,payload=96,media=video,encoding-name=H264,clock-rate=90000'
        )
        self.appsrc.set_property('caps', rtpcaps)

        def feed_appsrc(bus, msg):
            if len(self.payloads) == 0:
                self.appsrc.emit('end-of-stream')
            else:
                buf = Gst.Buffer.new_wrapped(self.payloads[0])
                self.appsrc.emit('push-buffer', buf)
                del(self.payloads[0])

        self.appsrc.connect('need-data', feed_appsrc)

        rtp_depayloader = Gst.ElementFactory.make('rtph264depay')
        h264_parser = Gst.ElementFactory.make('h264parse')
        h264_decoder = Gst.ElementFactory.make('avdec_h264')
        videoconvert = Gst.ElementFactory.make('videoconvert')

        self.appsink = Gst.ElementFactory.make('appsink')
        self.appsink.set_property('drop', True) # should we drop??
        self.appsink.set_property('max-buffers', MAX_BUFFERS)
        self.appsink.set_property('emit-signals', True)

        def get_appsink_data(sink):
            sample = sink.emit('pull-sample')
            if not sample:
                return
            buf = sample.get_buffer()
            status, info = buf.map(Gst.MapFlags.READ)
            if not status:
                raise Exception('H264_Decoder error: failed to map buffer data to GstMapInfo')
            self.frames.append(VideoFrame(0, 0, info.data))
            buf.unmap(info)

            return Gst.FlowReturn.OK

        self.appsink.connect('new-sample', get_appsink_data)

        self.pipeline.add(self.appsrc)
        self.pipeline.add(rtp_depayloader)
        self.pipeline.add(h264_parser)
        self.pipeline.add(h264_decoder)
        self.pipeline.add(videoconvert)
        self.pipeline.add(self.appsink)

        self.appsrc.link(rtp_depayloader)
        rtp_depayloader.link(h264_parser)
        h264_parser.link(h264_decoder)
        h264_decoder.link(videoconvert)
        videoconvert.link(self.appsink)

    def change_state(self, state):
        state = self.pipeline.set_state(state)
        if state == Gst.StateChangeReturn.FAILURE:
            raise Exception('H264_Encoder error: failed to change pipeline\'s state to', str(state))

    def __init__(self):
        self.payloads = []
        self.frames = []

        self.__create_pipeline()

        self.change_state(Gst.State.READY)

    def __del__(self):
        self.pipeline.set_state(Gst.State.NULL)

    def __update_frames_sizes(self):
        pad = self.appsink.get_static_pad('sink')
        caps = pad.get_current_caps()
        if caps is None:
            raise Exception('H264_Decoder error: appsink caps is somehow None - report this')
        structure = caps.get_structure(0)
        if structure is None:
            raise Exception('H264_Decoder error: appsink caps structure is somehow None - report this')

        w_status, width = structure.get_int('width')
        h_status, height = structure.get_int('height')

        if not w_status or not h_status:
            raise Exception('H264_Decoder error: could not extract frame width and height from appsink')

        for frame in self.frames:
            frame.width = width
            frame.height = height

    '''
    Decodes H.264 RTP payloads to a list of raw YUV420 frames

    :param payloads: list of binary representations of RTP payloads
    :returns: list of VideoFrame objects
    '''
    def decode(self, payloads):
        if len(payloads) == 0:
            raise Exception('H264_Decoder error: \'payloads\' length should be greater than 0')

        self.payloads = payloads

        self.change_state(Gst.State.PLAYING)

        msg = self.pipeline.get_bus().timed_pop_filtered(Gst.CLOCK_TIME_NONE,
            Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, _ = msg.parse_error()
                raise Exception('H264_Decoder error: pipeline failure: ' + err.message)
            elif msg.type != Gst.MessageType.EOS:
                raise Exception('H264_Decoder error: pipeline failure: unknown error')

        self.__update_frames_sizes()

        self.change_state(Gst.State.READY)

        current_frames = self.frames

        self.payloads = []
        self.frames = []

        return current_frames
