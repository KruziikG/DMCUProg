#coding: utf-8
import time


FLASH_KR = 0x40023C04
FLASH_SR = 0x40023C0C
FLASH_CR = 0x40023C10

FLASH_KR_KEY1 = 0x45670123
FLASH_KR_KEY2 = 0xCDEF89AB

FLASH_SR_BUSY   = (1 <<16)

FLASH_CR_WRITE  = (1 << 0)
FLASH_CR_SERASE = (1 << 1)  #Sect  Erase
FLASH_CR_CERASE = (1 << 2)  #Chip  Erase
FLASH_CR_ESTART = (1 <<16)  #Erase Start
FLASH_CR_LOCK   = (1 <<31)

FLASH_CR_SECT_MASK  = 0xFFFFFF07

FLASH_CR_PSIZE_MASK = 0xFFFFFCFF    # 烧写单位：字节、半字、字
FLASH_CR_PSIZE_BYTE = 0x00000000
FLASH_CR_PSIZE_HALF = 0x00000100
FLASH_CR_PSIZE_WORD = 0x00000200


class STM32F405RG(object):
    CHIP_CORE = 'Cortex-M4'

    PAGE_SIZE = 1024 * 4
    SECT_SIZE = 1024 * 16   # 实际并非16K，只用于生成界面下拉框
    CHIP_SIZE = 1024 * 1024

    @classmethod
    def addr2sect(cls, addr):
        if   addr < 1024 *  64:  return (addr             ) // (1024 *  16)
        elif addr < 1024 * 128:  return (addr - 1024 *  64) // (1024 *  64) + 4
        else:                    return (addr - 1024 * 128) // (1024 * 128) + 5

    def __init__(self, dap):
        super(STM32F405RG, self).__init__()
        
        self.dap = dap

    def unlock(self):
        self.dap.write32(FLASH_KR, FLASH_KR_KEY1)
        self.dap.write32(FLASH_KR, FLASH_KR_KEY2)

    def lock(self):
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) | FLASH_CR_LOCK)

    def wait_ready(self):
        while self.dap.read32(FLASH_SR) & FLASH_SR_BUSY:
            pass
    
    def sect_erase(self, addr, size):
        self.unlock()
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) & FLASH_CR_PSIZE_MASK)
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) | FLASH_CR_PSIZE_WORD)
        for i in range(self.addr2sect(addr), self.addr2sect(addr + size)):
            self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) & FLASH_CR_SECT_MASK)
            self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) | FLASH_CR_SERASE | (i << 3))
            self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) | FLASH_CR_ESTART)
            self.wait_ready()
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) &~FLASH_CR_SERASE)
        self.lock()

    def chip_write(self, addr, data):
        if len(data)%self.PAGE_SIZE:
            data = data + [0xFF] * (self.PAGE_SIZE - len(data)%self.PAGE_SIZE)

        self.sect_erase(addr, len(data))

        self.unlock()
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) | FLASH_CR_WRITE)
        for i in range(len(data)//4):
            self.dap.write32(0x08000000 + addr + i*4, data[i*4] | (data[i*4+1] << 8) | (data[i*4+2] << 16) | (data[i*4+3] << 24))
            self.wait_ready()
        self.dap.write32(FLASH_CR, self.dap.read32(FLASH_CR) &~FLASH_CR_WRITE)
        self.lock()
        
    def chip_read(self, addr, size, buff):
        data = self.dap.read_memory_block8(addr, size)

        buff.extend(data)
