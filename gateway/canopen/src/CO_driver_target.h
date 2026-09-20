/*
 * Device and application specific definitions for CANopenNode.
 *
 * @file        CO_driver_target.h
 * @author      Janez Paternoster
 * @copyright   2021 Janez Paternoster
 *
 * This file is part of <https://github.com/CANopenNode/CANopenNode>, a CANopen Stack.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not use this
 * file except in compliance with the License. You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License is
 * distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and limitations under the License.
 */

#ifndef CO_DRIVER_TARGET_H
#define CO_DRIVER_TARGET_H

/* This file contains device and application specific definitions. It is included from CO_driver.h, which contains
 * documentation for common definitions below. */

#include <stddef.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef CO_DRIVER_CUSTOM
#include "CO_driver_custom.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Stack configuration override default values. For more information see file CO_config.h. */

/* 项目以成熟核心栈处理 CiA301；本端口仅提供有界帧收发与单线程临界区。 */
#define CO_CONFIG_NMT CO_CONFIG_NMT_MASTER
#define CO_CONFIG_HB_CONS (CO_CONFIG_HB_CONS_ENABLE | CO_CONFIG_HB_CONS_QUERY_FUNCT | CO_CONFIG_HB_CONS_CALLBACK_MULTI)
#define CO_CONFIG_EM (CO_CONFIG_EM_PRODUCER | CO_CONFIG_EM_CONSUMER)
#define CO_CONFIG_SDO_SRV (CO_CONFIG_SDO_SRV_SEGMENTED)
#define CO_CONFIG_SDO_CLI (CO_CONFIG_SDO_CLI_ENABLE | CO_CONFIG_SDO_CLI_SEGMENTED)
#define CO_CONFIG_PDO (CO_CONFIG_RPDO_ENABLE | CO_CONFIG_TPDO_ENABLE | CO_CONFIG_TPDO_TIMERS_ENABLE | CO_CONFIG_PDO_OD_IO_ACCESS)
#define CO_CONFIG_SYNC 0
#define CO_CONFIG_TIME 0
#define CO_CONFIG_LEDS 0
#define CO_CONFIG_GFC 0
#define CO_CONFIG_SRDO 0
#define CO_CONFIG_LSS 0
#define CO_CONFIG_GTW 0
#define CO_CONFIG_TRACE 0
#define CO_CONFIG_NODE_GUARDING 0
#define CO_CONFIG_FIFO CO_CONFIG_FIFO_ENABLE
/* Basic definitions. If big endian, CO_SWAP_xx macros must swap bytes. */
#define CO_LITTLE_ENDIAN
#define CO_SWAP_16(x) x
#define CO_SWAP_32(x) x
#define CO_SWAP_64(x) x
/* NULL is defined in stddef.h */
/* true and false are defined in stdbool.h */
/* int8_t to uint64_t are defined in stdint.h */
typedef uint_fast8_t bool_t;
typedef float float32_t;
typedef double float64_t;

/* Access to received CAN frame */
typedef struct { uint16_t ident; uint8_t dlc; uint8_t data[8]; } MpCanFrame;
#define CO_CANrxMsg_readIdent(msg) (((MpCanFrame *)(msg))->ident)
#define CO_CANrxMsg_readDLC(msg) (((MpCanFrame *)(msg))->dlc)
#define CO_CANrxMsg_readData(msg) (((MpCanFrame *)(msg))->data)

/* Received frame object */
typedef struct {
    uint16_t ident;
    uint16_t mask;
    void* object;
    void (*CANrx_callback)(void* object, void* message);
} CO_CANrx_t;

/* Transmit frame object */
typedef struct {
    uint32_t ident;
    uint8_t DLC;
    uint8_t data[8];
    volatile bool_t bufferFull;
    volatile bool_t syncFlag;
} CO_CANtx_t;

/* CAN module object */
typedef struct {
    void* CANptr;
    CO_CANrx_t* rxArray;
    uint16_t rxSize;
    CO_CANtx_t* txArray;
    uint16_t txSize;
    uint16_t CANerrorStatus;
    volatile bool_t CANnormal;
    volatile bool_t useCANrxFilters;
    volatile bool_t bufferInhibitFlag;
    volatile bool_t firstCANtxMessage;
    volatile uint16_t CANtxCount;
    uint32_t errOld;
} CO_CANmodule_t;

/* Data storage object for one entry */
typedef struct {
    void* addr;
    size_t len;
    uint8_t subIndexOD;
    uint8_t attr;
    /* Additional variables (target specific) */
    void* addrNV;
} CO_storage_entry_t;

/* (un)lock critical section in CO_CANsend() */
#define CO_LOCK_CAN_SEND(CAN_MODULE)
#define CO_UNLOCK_CAN_SEND(CAN_MODULE)

/* (un)lock critical section in CO_errorReport() or CO_errorReset() */
#define CO_LOCK_EMCY(CAN_MODULE)
#define CO_UNLOCK_EMCY(CAN_MODULE)

/* (un)lock critical section when accessing Object Dictionary */
#define CO_LOCK_OD(CAN_MODULE)
#define CO_UNLOCK_OD(CAN_MODULE)

/* Synchronization between CAN receive and data processing threads. */
#define CO_MemoryBarrier()
#define CO_FLAG_READ(rxNew) ((rxNew) != NULL)
#define CO_FLAG_SET(rxNew)                                                                                             \
    {                                                                                                                  \
        CO_MemoryBarrier();                                                                                            \
        rxNew = (void*)1L;                                                                                             \
    }
#define CO_FLAG_CLEAR(rxNew)                                                                                           \
    {                                                                                                                  \
        CO_MemoryBarrier();                                                                                            \
        rxNew = NULL;                                                                                                  \
    }

#ifdef __cplusplus
}
#endif /* __cplusplus */

#endif /* CO_DRIVER_TARGET_H */
