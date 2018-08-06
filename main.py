import time
import os

from h264 import *

# Example usage of the library

if __name__ == '__main__':
    Gst.init(None)

    # ===========Recording and encoding 5 seconds of footage from the webcam===========

    encoder = H264_Encoder()

    pipeline = Gst.Pipeline.new(None)
    # v4l2src ! image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! rawvideoparse width=1280 height=720 framerate=30/1 ! appsink

    webcam = Gst.ElementFactory.make('v4l2src')

    caps = Gst.Caps.from_string('image/jpeg,width=1280,height=720,framerate=30/1')
    capsfilter = Gst.ElementFactory.make('capsfilter')
    capsfilter.set_property('caps', caps)

    jpegdec = Gst.ElementFactory.make('jpegdec')

    videoparse = Gst.ElementFactory.make('rawvideoparse')
    videoparse.set_property('width', 1280)
    videoparse.set_property('height', 720)
    videoparse.set_property('framerate', Gst.Fraction(30))

    appsink = Gst.ElementFactory.make('appsink')
    sinkcaps = Gst.Caps.from_string(
        'video/x-raw,format=I420,width=1280,height=720,framerate=30/1'
    )
    appsink.set_property('caps', sinkcaps)
    appsink.set_property('drop', True)
    appsink.set_property('emit-signals', True)
    webcam_frames = []
    payloads = []

    def get_appsink_data(sink):
        sample = sink.emit('pull-sample')
        if not sample:
            return
        buf = sample.get_buffer()
        _, info = buf.map(Gst.MapFlags.READ)
        frame = VideoFrame(1280, 720, info.data)
        webcam_frames.append(frame)
        payloads.extend(encoder.encode([frame]))
        buf.unmap(info)

        return Gst.FlowReturn.OK

    appsink.connect('new-sample', get_appsink_data)

    pipeline.add(webcam)
    pipeline.add(capsfilter)
    pipeline.add(jpegdec)
    pipeline.add(videoparse)
    pipeline.add(appsink)

    webcam.link(capsfilter)
    capsfilter.link(jpegdec)
    jpegdec.link(videoparse)
    videoparse.link(appsink)

    pipeline.set_state(Gst.State.PLAYING)
    time.sleep(5)
    pipeline.set_state(Gst.State.NULL)

    print('Encoded 5 seconds of webcam footage!')
    print(len(webcam_frames), 'frames and', len(payloads), 'payloads in total.')
    print('Decoding now...')

    # ===========Decoding the encoded webcam footage===========

    decoder = H264_Decoder()
    decoded_frames = decoder.decode(payloads)

    print('Decoded!', len(decoded_frames), 'frames in total.')

    if not os.path.isdir('cam'):
        os.mkdir('cam')

    print('Writing original frame #50...')
    with open('cam/original.yuv', 'wb') as file:
        file.write(webcam_frames[50].data)

    print('Writing decoded frame #50...')
    with open('cam/decoded.yuv', 'wb') as file:
        file.write(decoded_frames[50].data)

    # ===========Displaying the decoded footage===========

    print('Displaying the decoded result...')

    pipeline = Gst.Pipeline.new(None)
    # appsrc -> rawvideoparse -> xvimagesink

    appsrc = Gst.ElementFactory.make('appsrc')
    srccaps = Gst.Caps.from_string('video/x-raw,format=I420,width=1280,height=720,framerate=30/1')
    appsrc.set_property('caps', srccaps)

    def frame_generator():
        for frame in decoded_frames:
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

    videoparse = Gst.ElementFactory.make('rawvideoparse')
    videoparse.set_property('width', 1280)
    videoparse.set_property('height', 720)
    videoparse.set_property('framerate', Gst.Fraction(30))

    xvimagesink = Gst.ElementFactory.make('xvimagesink')

    pipeline.add(appsrc)
    pipeline.add(videoparse)
    pipeline.add(xvimagesink)

    appsrc.link(videoparse)
    videoparse.link(xvimagesink)

    pipeline.set_state(Gst.State.PLAYING)
    bus = pipeline.get_bus()
    bus.timed_pop_filtered(Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS)
    pipeline.set_state(Gst.State.NULL)
