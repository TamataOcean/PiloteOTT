#include "sysfs_gpio.h"
#include <stdlib.h> // exit()
#include <stdio.h> // printf()
#include <stdint.h> // uint8_t
#include <unistd.h> // sleep()
#include <signal.h> // signal()

//GPIO
uint8_t Relay[] = {GPIO5, GPIO6, GPIO13, GPIO16, GPIO19, GPIO20, GPIO21, GPIO26};

void  Handler(int signo)
{
    //System Exit
    printf("\r\nHandler:exit...\r\n");
    for(int i=0; i<8; i++)  {
        SYSFS_GPIO_Unexport(Relay[i]);
    }
    exit(0);
}

int main(int argc, char **argv)
{    
    uint8_t i;

    // Exception handling:ctrl + c
    signal(SIGINT, Handler);
    
    printf("GPIO config\r\n");
    //GPIO config
    for(i=0; i<8; i++)  {
        SYSFS_GPIO_Export(Relay[i]);
        SYSFS_GPIO_Direction(Relay[i], OUT);
        SYSFS_GPIO_Write(Relay[i], HIGH);
    }

    while(1) {
        for(i=0; i<8; i++)  {
            printf("Write %d = %d\r\n", Relay[i], LOW);
            SYSFS_GPIO_Write(Relay[i], LOW);
            sleep(1);
        }

        for(i=0; i<8; i++)  {
            printf("Write %d = %d\r\n", Relay[i], HIGH);
            SYSFS_GPIO_Write(Relay[i], HIGH);
            sleep(1);
        }
    }

    return 0;
}
