import av
import math

def __data_from_av_frame(frame):
    data = bytearray()
    for plane in frame.planes:
        data += bytearray(plane)
    return data

def __data_to_av_frame(data, width, height, frame=None):
    U_beg = width * height
    Y_beg = U_beg + U_beg // 4

    Y = data[:U_beg]
    U = data[U_beg:Y_beg]
    V = data[Y_beg:]

    if frame is None:
        frame = av.VideoFrame(width, height, 'yuv420p')

    YUV = [Y, U, V]
    for i in range(0, len(YUV)):
        frame.planes[i].update_buffer(YUV[i])

    return frame

class VideoFrame:
    def __init__(self, width, height, data=None):
        self.width = width
        self.height = height

        if data:
            self.data = data
        else:
            self.data = b'\x00' * math.ceil(width * height * 12 / 8)

class H264_Payload_Descriptor:
    def __init__(self):
        pass

    def __bytes__(self):
        pass

    def __repr__(self):
        pass

    @classmethod
    def parse(cls, data):
        pass

class H264_Decoder:
    def __init__(self):
        pass

    def decode(self, payloads):
        pass

class H264_Encoder:
    def __init__(self):
        pass

    def encode(self, frames):
        pass
