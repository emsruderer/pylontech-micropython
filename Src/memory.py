import sys
import gc
import os
import time
import _thread
import logging

STOP = False
KILO = 1000

loging = logging.getLogger('memory')
logging.setLevel(logging.DEBUG)

def check_ram():
    gc.enable()
    logging.warning(f"allocated sram = {gc.mem_alloc()/KILO:10.1f} kB")
    logging.warning(f"free sram      = {gc.mem_free()/KILO:10.1f} kB")
    gc.collect()

def check_pico_storage():
    """UF2 uses around 1.3 mB, so 700 kB rests as filesystem"""
    result=os.statvfs('/')
    block_size=result[0]
    total_blocks=result[2]
    free_blocks=result[3]
    total_size=total_blocks*block_size/KILO
    free_size=free_blocks*block_size/KILO
    logging.warning(f'flash total_size = {total_size:5.1f} kB')
    logging.warning(f'flash free_size  = {free_size:5.1f} kB')

def check_memory():
    try :
      while not STOP:
        check_ram()
        check_pico_storage()
        time.sleep(60)
    except exception as ex:
        logging.exception(ex)

def memory_thread():
    try:
        thr = _thread.start_new_thread(check_memory,())
    except Exception as ex:
       logging.exception(ex)
       STOP = True
       thr.exit()

        
