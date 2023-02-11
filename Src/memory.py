import logging
logger = logging.getLogger("memory","memory.log")
logger.setLevel(logging.INFO)

import sys
import gc
import os
import time
import _thread

KILO = 1000
STOP = False

def check_ram():
    gc.enable()
    gc.mem_alloc()
    logger.info(f"allocated sram = {gc.mem_alloc()/KILO:10.1f} kB")
    logger.info(f"free sram      = {gc.mem_free()/KILO:10.1f} kB")
    gc.collect()

def check_pico_storage():
    """UF2 uses around 1.3 mB, so 700 kB rests as filesystem"""
    result=os.statvfs('/')
    block_size=result[0]
    total_blocks=result[2]
    free_blocks=result[3]
    total_size=total_blocks*block_size/KILO
    free_size=free_blocks*block_size/KILO
    logger.info(f'flash total_size = {total_size:5.1f} kB')
    logger.info(f'flash free_size  = {free_size:5.1f} kB')

def check_memory():
    try :
      while not STOP:
        check_ram()
        check_pico_storage()
        time.sleep(60)
      return
    except Exception as ex:
        logger.exception(ex,'%s function check_memory', "this")
        

def memory_thread():
    try:
        thr = _thread.start_new_thread(check_memory,())
        return thr
    except Exception as ex:
       logger.exception(ex,"%s is an exception in memory_thread","this")
       STOP = True
       thr.exit()

        
if __name__ == '__main__':
    try:
        thr=memory_thread()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        STOP = True
        #thr.exit()
        