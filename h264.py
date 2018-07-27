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
    def __create_pipeline(frames, framerate=0):
        if len(frames) == 0:
            raise Exception('H264_Encoder error: \'frames\' length should be greater than 0')

        width = frames[0].width
        height = frames[0].height

        pipeline = Gst.Pipeline.new()
        # appsrc -> videoparse -> videoconvert -> x264enc -> rtph264pay -> appsink

        appsrc = Gst.ElementFactory.make('appsrc')
        def frame_generator():
            for frame in frames:
                yield frame.data

        generator = frame_generator()

        def feed_appsrc(bus, msg):
            try:
                frame = next(generator)
                buf = Gst.Buffer.new_wrapped(frame)
                appsrc.emit('push-buffer', buf)
            except StopIteration:
                appsrc.emit('end-of-stream')

        appsrc.connect('need-data', feed_appsrc)

        srccaps = Gst.Caps.from_string(
            'video/x-raw,format=I420,width={},height={},framerate={}/1'.format(
                width,
                height,
                str(framerate)
            )
        )
        appsrc.set_property('caps', srccaps)

        videoparse = Gst.ElementFactory.make('videoparse')
        videoparse.set_property('width', width)
        videoparse.set_property('height', height)
        videoparse.set_property('framerate', Gst.Fraction(framerate))

        videoconvert = Gst.ElementFactory.make('videoconvert')
        x264_encoder = Gst.ElementFactory.make('x264enc')
        rtp_payloader = Gst.ElementFactory.make('rtph264pay')

        appsink = Gst.ElementFactory.make('appsink')
        appsink.set_property('drop', True) # should we drop??
        appsink.set_property('max-buffers', MAX_BUFFERS)
        appsink.set_property('emit-signals', True)
        rtpcaps = Gst.Caps.from_string(
            'application/x-rtp,payload=96,media=video,encoding-name=H264,clock-rate=90000'
        )
        appsink.set_property('caps', rtpcaps)

        pipeline.add(appsrc)
        pipeline.add(videoparse)
        pipeline.add(videoconvert)
        pipeline.add(x264_encoder)
        pipeline.add(rtp_payloader)
        pipeline.add(appsink)

        appsrc.link(videoparse)
        videoparse.link(videoconvert)
        videoconvert.link(x264_encoder)
        x264_encoder.link(rtp_payloader)
        rtp_payloader.link(appsink)

        return pipeline, appsrc, appsink


    '''
    Encodes raw video frames with H.264 and packages the result in RTP payloads

    :param frames: list of VideoFrame objects
    :returns: list of binary representations of RTP payloads
    '''
    def encode(self, frames):
        pipeline, appsrc, appsink = self.__create_pipeline(frames, 60) # TODO: change parameters later

        payloads = []
        def get_appsink_data(sink):
            sample = sink.emit('pull-sample')
            if not sample:
                return
            buf = sample.get_buffer()
            status, info = buf.map(Gst.MapFlags.READ)
            if not status:
                raise Exception('H264_Encoder error: failed to map buffer data to GstMapInfo')
            payloads.append(info.data)
            buf.unmap(info)

            return 0

        appsink.connect('new-sample', get_appsink_data)

        state = pipeline.set_state(Gst.State.PLAYING)

        if state == Gst.StateChangeReturn.FAILURE:
            raise Exception('H264_Encoder error: failed to set pipeline\'s state to PLAYING')

        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,
            Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, _ = msg.parse_error()
                raise Exception('H264_Encoder error: pipeline failure: ' + err.message)
            elif msg.type != Gst.MessageType.EOS:
                raise Exception('H264_Encoder error: pipeline failure: unknown error')

        #pad = rtp_payloader.get_static_pad('sink')
        #encoded_caps = pad.get_current_caps()

        pipeline.set_state(Gst.State.NULL)

        return payloads

##############################################################################

class H264_Decoder:
    @staticmethod
    def __create_pipeline(payloads):
        if len(payloads) == 0:
            raise Exception('H264_Decoder error: \'payloads\' length should be greater than 0')

        pipeline = Gst.Pipeline.new()
        # appsrc -> rtph264depay -> h264parse -> avdec_h264 -> videoconvert -> appsink

        appsrc = Gst.ElementFactory.make('appsrc')
        def payload_generator():
            for payload in payloads:
                yield payload

        generator = payload_generator()

        def feed_appsrc(bus, msg):
            try:
                payload = next(generator)
                print('Wrapping next payload...')
                buf = Gst.Buffer.new_wrapped(payload)
                appsrc.emit('push-buffer', buf)
            except StopIteration:
                appsrc.emit('end-of-stream')

        appsrc.connect('need-data', feed_appsrc)

        rtpcaps = Gst.Caps.from_string(
            'application/x-rtp,payload=96,media=video,encoding-name=H264,clock-rate=90000'
        )
        appsrc.set_property('caps', rtpcaps)

        rtp_depayloader = Gst.ElementFactory.make('rtph264depay')
        h264_parser = Gst.ElementFactory.make('h264parse')
        h264_decoder = Gst.ElementFactory.make('avdec_h264')
        videoconvert = Gst.ElementFactory.make('videoconvert')
        appsink = Gst.ElementFactory.make('appsink')
        appsink.set_property('drop', True) # should we drop??
        appsink.set_property('max-buffers', MAX_BUFFERS)
        appsink.set_property('emit-signals', True)

        fakesink = Gst.ElementFactory.make('fakesink')

        pipeline.add(appsrc)
        pipeline.add(rtp_depayloader)
        pipeline.add(fakesink)
        appsrc.link(rtp_depayloader)
        rtp_depayloader.link(fakesink)

        '''
        pipeline.add(rtp_depayloader)
        pipeline.add(h264_parser)
        pipeline.add(h264_decoder)
        pipeline.add(videoconvert)
        pipeline.add(appsink)
        '''
        '''
        appsrc.link(rtp_depayloader)
        rtp_depayloader.link(h264_parser)
        h264_parser.link(h264_decoder)
        h264_decoder.link(videoconvert)
        videoconvert.link(appsink)
        '''
        return pipeline, appsrc, appsink


    def decode(self, payloads):
        pipeline, appsrc, appsink = self.__create_pipeline(payloads)

        frames = []
        def get_appsink_data(sink):
            sample = sink.emit('pull-sample')
            if not sample:
                print('No sample!')
            buf = sample.get_buffer()
            status, info = buf.map(Gst.MapFlags.READ)
            if not status:
                raise Exception('H264_Decoder error: failed to map buffer data to GstMapInfo')
            frames.append(info.data) # TODO: save as VideoFrame objects
            print('Appended to frames -', len(frames))

            return 0

        appsink.connect('new-sample', get_appsink_data)

        state = pipeline.set_state(Gst.State.PLAYING)
        if state == Gst.StateChangeReturn.FAILURE:
            raise Exception('H264_Decoder error: failed to set pipeline\'s state to PLAYING')

        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE,
            Gst.MessageType.ERROR | Gst.MessageType.EOS)
        if msg:
            if msg.type == Gst.MessageType.ERROR:
                err, _ = msg.parse_error()
                raise Exception('H264_Decoder error: pipeline failure: ' + err.message)
            elif msg.type != Gst.MessageType.EOS:
                raise Exception('H264_Decoder error: pipeline failure: unknown error')

        pipeline.set_state(Gst.State.NULL)

        return frames
