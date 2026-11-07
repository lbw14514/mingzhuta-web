"""THA1 (th15.dat) 解包器 按重实现 Archive.cpp/Lzss.cpp 语义移植"""
import struct

CIPHERS=[(27,115,256,14336),(18,67,512,15872),(53,121,1024,15360),(3,145,128,25600),
         (171,220,128,28672),(81,158,256,16384),(193,21,1024,11264),(153,125,128,17408)]

def resource_crypt(data,params,encrypt=False):
    key,step,block,limit=params
    size=len(data)
    out=bytearray(data)
    untouched=(size%block if size%block<block//4 else 0)+(size&1)
    remaining=size-untouched
    cursor=0
    while remaining>0 and limit>0:
        b=min(block,remaining)
        linear=0
        for parity in (1,2):
            for pos in range(b-parity,-1,-2):
                if encrypt: out[cursor+linear]=data[cursor+pos]^key
                else: out[cursor+pos]=data[cursor+linear]^key
                key=(key+step)&0xFF
                linear+=1
        cursor+=b; remaining-=b; limit-=b
    return bytes(out)

def lzss_decode(data,capacity):
    # Lzss::decode 语义 字典 8192 head 初始 1 位流 MSB first EOF 后补零
    dic=bytearray(8192)
    out=bytearray()
    cursor=0;head=1;buffer=0;available=0
    size=len(data)
    def bits(n):
        nonlocal buffer,available,cursor
        while available<n:
            buffer=((buffer<<8)|(data[cursor] if cursor<size else 0))&0xFFFFFFFFFFFF
            cursor+=1;available+=8
        available-=n
        return (buffer>>available)&((1<<n)-1)
    def put(v):
        nonlocal head
        out.append(v)
        dic[head]=v;head=(head+1)&8191
    while True:
        if bits(1):
            if len(out)==capacity: return None
            put(bits(8))
        else:
            offset=bits(13)
            if offset==0: return bytes(out)
            length=bits(4)+3
            if length>capacity-len(out): return None
            for i in range(length):
                put(dic[(offset+i)&8191])

class Tha1:
    def __init__(self,path):
        self.data=open(path,'rb').read()
        hdr=resource_crypt(self.data[:16],(27,55,16,16))
        assert hdr[:4]==b'THA1',hdr[:4]
        self.unpacked=struct.unpack_from('<I',hdr,4)[0]-123456789
        self.packed=struct.unpack_from('<I',hdr,8)[0]-987654321
        self.count=struct.unpack_from('<I',hdr,12)[0]-135792468
        self.table_off=len(self.data)-self.packed
        enc=resource_crypt(self.data[self.table_off:],(62,155,128,self.packed))
        table=lzss_decode(enc,self.unpacked)
        assert table is not None and len(table)==self.unpacked
        self.entries=[]
        cursor=0
        last_off=None
        for i in range(self.count):
            begin=cursor
            while cursor<len(table) and table[cursor]!=0: cursor+=1
            name=table[begin:cursor].decode('ascii')
            cursor=begin+((cursor-begin+4)&~3)
            off,size,rsv=struct.unpack_from('<III',table,cursor)
            cursor+=12
            self.entries.append({'name':name,'offset':off,'size':size,'reserved':rsv})
        for i,e in enumerate(self.entries):
            nxt=self.entries[i+1]['offset'] if i+1<len(self.entries) else self.table_off
            e['compressed']=nxt-e['offset']
    def read(self,name):
        for e in self.entries:
            if e['name']==name:
                s=e['compressed']
                key=sum(name.encode('ascii'))&7
                dec=resource_crypt(self.data[e['offset']:e['offset']+s],CIPHERS[key])
                if s==e['size']: return dec
                return lzss_decode(dec,e['size'])
        raise KeyError(name)

if __name__=='__main__':
    import sys
    a=Tha1(r'C:/touhou15-web-port/th15/[th15] 东方绀珠传 (汉化版+日文版)/th15.dat')
    print('条目',len(a.entries),'表',a.unpacked,'packed',a.packed)
    print('前 10 个:')
    for e in a.entries[:10]: print(' ',e['name'],e['size'])
    tl=[e['name'] for e in a.entries if 'title' in e['name'].lower()]
    print('title 相关:',tl)
