#include <wiringPi.h>
#include <stdio.h>

int Relay[] = {5, 6, 13, 16, 19, 20, 21, 26};

int main(void)  {

    int i;

    if(wiringPiSetupGpio() < 0) {
        printf("GPIO init error !\r\n");
        return 1;
    }
    printf("GPIO init success !\r\n");
    
    for(i=0; i<8; i++)  {
        pinMode(Relay[i], OUTPUT);
        digitalWrite(Relay[i],HIGH);
    }
    delay(500);


    while(1)    {

        for(i=0; i<8; i++)  {
            digitalWrite(Relay[i],LOW);
            delay(500);
        }
        for(i=0; i<8; i++)  {
            digitalWrite(Relay[i],HIGH);
            delay(500);
        }
    }
}



