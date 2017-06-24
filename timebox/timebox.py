import bluetooth
import time
import click
import math
from colour import Color
from itertools import product
from os import listdir
from os.path import isfile, join
from PIL import Image
from binascii import unhexlify
from math import modf

class Timebox:
    debug=False
    def __init__(self, addr):
        self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.addr = addr

    def connect(self):
        self.sock.connect((self.addr, 4))

    def disconnect(self):
        self.sock.close()

    def send(self, package):
        if(self.debug):
            print([hex(b)[2:].zfill(2) for b in package])
        self.sock.send(str(bytearray(package)))

    def send_raw(self, bts):
        self.sock.send(bts)


VIEWTYPES = {
            "clock": 0x00,
            "temp": 0x01,
            "off": 0x02,
            "anim": 0x03,
            "graph": 0x04,
            "image": 0x05,
            "stopwatch": 0x06,
            "scoreboard": 0x07
}


@click.group()
@click.argument('address', nargs=1)
@click.option('--debug', is_flag=True)
@click.option('--disconnect', 'disconnect', flag_value=True, default=True)
@click.option('--keepconnected', 'disconnect', flag_value=False, default=True)
@click.pass_context
def cli(ctx, address, debug,disconnect):
    ctx.obj['address']=address
    dev = connect(ctx.obj['address'])
    if(debug):
        dev.debug=True
    ctx.obj['dev']=dev
    
    return dev, disconnect

@cli.command(short_help='change view')
@click.argument('type', nargs=1)
@click.pass_context
def view(ctx, type):
    if(type in VIEWTYPES):
        ctx.obj['dev'].send(switch_view(type))



@cli.command(short_help='display time')
@click.option('--color', nargs=1)
@click.option('--ampm', is_flag=True, help="12h format am/pm")
@click.pass_context
def clock(ctx, color, ampm):
    if(color):
        c = color_convert(Color(color).get_rgb())
        ctx.obj['dev'].send(set_time_color(c[0],c[1],c[2],0xff,not ampm))
    else:
        ctx.obj['dev'].send(switch_view("clock"))
       
        
@cli.command(short_help='display temperature, set color')
@click.option('--color', nargs=1)
@click.option('--f', is_flag=True, help="12 format am/pm")
@click.pass_context
def temp(ctx, color, f):    
    if(color):
        c = color_convert(Color(color).get_rgb())
        ctx.obj['dev'].send(set_temp_color(c[0],c[1],c[2],0xff,f))
    else:
        ctx.obj['dev'].send(switch_view("temp"))


def switch_view(type):
    h = [0x04, 0x00, 0x45, VIEWTYPES[type]]
    ck1, ck2 = checksum(sum(h))
    return [0x01] + mask(h) + mask([ck1, ck2]) +[0x02]

        
#0x01 Start of message
#0x02 End of Message
#0x03 Mask following byte

def color_comp_conv(cc):
    cc = max(0.0, min(1.0, cc))
    return int(math.floor(255 if cc == 1.0 else  cc * 256.0))

def color_convert(rgb):
    return [ color_comp_conv(c) for c in rgb ]


def unmask(bytes, index=0):
    try:
        index=bytes.index(0x03,index)
    except ValueError:
        return bytes
    
    _bytes = bytes[:]
    _bytes[index+1]=_bytes[index+1]-0x03
    _bytes.pop(index)
    return unmask(_bytes,index+1)
        

def mask(bytes):
    _bytes = []
    for b in bytes:
        if(b==0x01):
            _bytes=_bytes+[0x03,0x04]
        elif(b==0x02):
            _bytes=_bytes+[0x03,0x05]
        elif(b==0x03):
            _bytes=_bytes+[0x03,0x06]
        else:
            _bytes+=[b]
        
    return _bytes

def checksum(s):
    ck1 = s & 0x00ff
    ck2 = s >> 8
    
    return ck1, ck2

def set_time_color(r,g,b,x=0x00,h24=True):
    head = [0x09,0x00,0x45,0x00,0x01 if h24 else 0x00]
    s=sum(head)+sum([r,g,b,x])
    ck1, ck2 = checksum(s)
    
    #create message mask 0x01,0x02,0x03
    msg = [0x01]+mask(head)+mask([r,g,b,x])+mask([ck1,ck2])+[0x02]
    
    return msg

def set_temp_color(r,g,b,x,f=False):
    head = [0x09,0x00,0x45,0x01,0x01 if f else 0x00]
    s=sum(head)+sum([r,g,b,x])
    ck1, ck2 = checksum(s)
    
    #create message mask 0x01,0x02,0x03
    msg = [0x01]+mask(head)+mask([r,g,b,x])+mask([ck1,ck2])+[0x02]
    
    return msg


def analyseImage(im):
    '''
    Pre-process pass over the image to determine the mode (full or additive).
    Necessary as assessing single frames isn't reliable. Need to know the mode
    before processing all frames.
    '''
    results = {
        'size': im.size,
        'mode': 'full',
    }
    try:
        while True:
            if im.tile:
                tile = im.tile[0]
                update_region = tile[1]
                update_region_dimensions = update_region[2:]
                if update_region_dimensions != im.size:
                    results['mode'] = 'partial'
                    break
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    im.seek(0)
    return results


def getFrames(im):
    '''
    Iterate the GIF, extracting each frame.
    '''
    mode = analyseImage(im)['mode']

    p = im.getpalette()
    last_frame = im.convert('RGBA')

    try:
        while True:
            '''
            If the GIF uses local colour tables, each frame will have its own palette.
            If not, we need to apply the global palette to the new frame.
            '''
            if not im.getpalette():
                im.putpalette(p)

            new_frame = Image.new('RGBA', im.size)

            '''
            Is this file a "partial"-mode GIF where frames update a region of a different size to the entire image?
            If so, we need to construct the new frame by pasting it on top of the preceding frames.
            '''
            if mode == 'partial':
                new_frame.paste(last_frame)

            new_frame.paste(im, (0,0), im.convert('RGBA'))
            yield new_frame

            last_frame = new_frame
            im.seek(im.tell() + 1)
    except EOFError:
        pass


def process_image(imagedata,sz=11,scale=None):
    img = [0]
    bc = 0
    first=True
    
    if(scale):
        src = imagedata.resize((sz, sz), scale)
    else:
        src = imagedata.resize((sz, sz))
        
    for c in product(range(sz),range(sz)):
        y,x = c
        r,g,b,a = src.getpixel((x,y))
            
        if(first):
            img[-1] = ((r&0xf0)>>4)+(g&0xf0) if a>32 else 0
            img.append((b&0xf0)>>4) if a>32 else img.append(0)
            first=False
        else:
            img[-1] += (r&0xf0) if a>32 else 0
            img.append(((g&0xf0)>>4)+(b&0xf0)) if a>32 else img.append(0)
            img.append(0)
            first=True
        bc += 1
    return img


def load_image(file, sz=11, scale=None):
    with Image.open(file).convert("RGBA") as imagedata:
        return process_image(imagedata,sz)
    
def load_gif_frames(file,sz=11,scale=None):
    with Image.open(file) as imagedata:
        for f in getFrames(imagedata):
            yield process_image(f,sz,scale)


def conv_image(data):    
    # should be 11x11 px => 
    head = [0xbd,0x00,0x44,0x00,0x0a,0x0a,0x04]
    data = data
    ck1,ck2 = checksum(sum(head)+sum(data))
    
    msg = [0x01]+head+mask(data)+mask([ck1,ck2])+[0x02]
    return msg


def prepare_animation(frames, delay=0):
    head = [0xbf,0x00,0x49,0x00,0x0a,0x0a,0x04]
    
    ret = []
    
    fi = 0
    for f in frames:
        _head = head+[fi,delay]
        ck1,ck2 = checksum(sum(_head)+sum(f))
        msg=[0x01]+mask(_head)+mask(f)+mask([ck1,ck2])+[0x02]
        fi+=1
        ret.append(msg)
        
    return ret

@cli.command(short_help='display_image')
@click.argument('file', nargs=1)
@click.pass_context
def image(ctx, file):
    ctx.obj['dev'].send(conv_image(load_image(file,scale=Image.BICUBIC)))
    
    
@cli.command(short_help='display_animation')
@click.option('--gif', 'source', flag_value='gif')
@click.option('--folder', 'source', flag_value='folder',default=True)
@click.option('--delay', nargs=1)
@click.argument('path', nargs=1)
@click.pass_context
def animation(ctx, source, path, delay):
    frames = []
    
    if(source=="folder"):
        for f in listdir(path):
            f=join(path, f)
            if isfile(f):
                frames.append(load_image(f))
    elif(source=="gif"):
        for f in load_gif_frames(path,11,scale=Image.BICUBIC):
            frames.append(f)
    
    for f in prepare_animation(frames,delay=int(delay) if delay else 0):
        ctx.obj['dev'].send(f)


# TODO: a bit weird, if the animation has "less frames than usual", it might be "glued" to the previous ;)
@cli.command(short_help='control fmradio')
@click.option('--on', 'state', flag_value=True, default=True)
@click.option('--off', 'state', flag_value=False)
@click.option('--frequency', nargs=1)
@click.pass_context
def fmradio(ctx, state, frequency):
    if(state):
        ctx.obj['dev'].send([0x01]+mask([0x04,0x00,0x05,0x01,0x0a,0x00])+[0x02])
        if(frequency):
            # TODO: WIP! setting frequency does not yet work as expected
            frequency=float(frequency)
            head = [0x05,0x00]
            frac, whole = modf(frequency)
            frac=int(frac*100)
            whole=(int(whole))
            f=[whole,frac]
            print f
            print mask(f)
            ck1,ck2 = checksum(sum(head)+sum(f))
            print [ck1,ck2]
            print mask([ck1,ck2])
            ctx.obj['dev'].send([0x01]+head+mask(f)+mask([ck1,ck2])+[0x02])
    else:
        ctx.obj['dev'].send([0x01]+mask([0x04,0x00,0x05,0x00,0x09,0x00])+[0x02])



@cli.command(short_help='raw message')
@click.option('--mask', '_mask', is_flag=True)
@click.argument('hexbytes', nargs=1)
@click.pass_context
def raw(ctx, hexbytes, _mask):    
    if(_mask):
        ctx.obj['dev'].send(mask(unhexlify(hexbytes)))
    else:
        ctx.obj['dev'].send(unhexlify(hexbytes))

def connect(address):
    dev = Timebox(address)
    dev.connect()

    return dev


if __name__ == '__main__':
    dev, disconnect = cli(obj={})
    if(disconnect):
        dev.disconnect()


