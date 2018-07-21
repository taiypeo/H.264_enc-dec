import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import math

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
    def __create_pipeline(frames, framerate=0, format='I420'):
        if len(frames) == 0:
            raise Exception('H264_Encoder error: \'frames\' length should be greater than 0')

        width = frames[0].width
        height = frames[0].height

        pipeline = Gst.Pipeline.new()
        # appsrc - capsfilter - videoconvert - x264enc - rtp_payloader - appsink

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

        caps = Gst.Caps.from_string(
            'video/x-raw,format={},width={},height={},framerate={}/1'.format(
                format,
                width,
                height,
                str(framerate)
            )
        )
        capsfilter = Gst.ElementFactory.make('capsfilter')
        capsfilter.set_property('caps', caps)
        videoconvert = Gst.ElementFactory.make('videoconvert')
        x264_encoder = Gst.ElementFactory.make('x264enc')
        rtp_payloader = Gst.ElementFactory.make('rtph264pay')
        appsink = Gst.ElementFactory.make('appsink')

        pipeline.add(appsrc)
        pipeline.add(capsfilter)
        pipeline.add(videoconvert)
        pipeline.add(x264_encoder)
        #pipeline.add(rtp_payloader)
        #pipeline.add(appsink)
        filesink = Gst.ElementFactory.make('filesink')
        filesink.set_property('location', 'out.264')
        pipeline.add(filesink)

        appsrc.link(capsfilter)
        capsfilter.link(videoconvert)
        videoconvert.link(x264_encoder)
        #x264_encoder.link(rtp_payloader)
        #rtp_payloader.link(appsink)
        x264_encoder.link(filesink)

        # pipeline.set_state(Gst.State.PLAYING)

        return pipeline, appsrc, appsink

    def encode(self, frames):
        if len(frames) == 0:
            raise Exception('H264_Encoder error: \'frames\' length should be greater than 0')

        pipeline, appsrc, appsink = self.__create_pipeline(frames, 28, 'YUY2')
        # do stuff

        pipeline.set_state(Gst.State.PLAYING)
