// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

#ifdef __linux__
#include <stdio_ext.h>  // For _fpurge() function
#endif

int isFileExist (const char *filename) {
    if ( access (filename, F_OK) != -1 ) { // file exists
        return 1;
    } else { // file doesn't exist
        return 0;
    }
}

time_t toEpochTime (int date, int month, int year, int hour, int minute, int second) {
    struct tm timeinfo = {0};
    time_t result = 0;
    timeinfo.tm_sec = second;
    timeinfo.tm_min = minute;
    timeinfo.tm_hour = hour;
    timeinfo.tm_mday = date;
    timeinfo.tm_mon = month - 1;
    timeinfo.tm_year = year - 1900;
    result = mktime (&timeinfo);
    return result;
}

void toDateMonthYear (time_t epochTime, int *date, int *month, int *year) {
    struct tm *timeinfo;
    timeinfo = localtime (&epochTime);
    *date = timeinfo->tm_mday;
    *month = timeinfo->tm_mon + 1;
    *year = timeinfo->tm_year + 1900;
}

time_t nDayRollbackToDateMonthYear (int date, int month, int year, int nDayRollback) {
    struct tm timeinfo = {0};
    time_t result = 0;
    timeinfo.tm_sec = 59;
    timeinfo.tm_min = 59;
    timeinfo.tm_hour = 23;
    timeinfo.tm_mday = date - nDayRollback;
    timeinfo.tm_mon = month - 1;
    timeinfo.tm_year = year - 1900;
    result = mktime (&timeinfo);
    return result;
}

time_t nMonthRollbackToDateMonthYear (int date, int month, int year, int nMonthRollback) {
    struct tm timeinfo = {0};
    time_t result = 0;
    timeinfo.tm_sec = 59;
    timeinfo.tm_min = 59;
    timeinfo.tm_hour = 23;
    timeinfo.tm_mday = date;
    timeinfo.tm_mon = month - 1 - nMonthRollback;
    timeinfo.tm_year = year - 1900;
    result = mktime (&timeinfo);
    return result;
}

int getProperTimeRollingInDay (int date, int month, int year, int maxRolling) {
    int numberOfTransactionRecords = RecordCount.transaction;
    time_t startTime, endTime;
    int i, roll = maxRolling + 1;
    while(roll--){
        startTime = toEpochTime (date - roll, month, year, 0, 0, 0);   // From: dd/mm/yyyy 00:00:00
        endTime = toEpochTime (date - roll, month, year, 23, 59, 59);  // To:   dd/mm/yyyy 23:59:59
        for ( i = 0;
              i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
            if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
                // If the record is in the time range
                return roll;
            }
        }
    }
    return 0;
}

int getProperTimeStartInMonth (int monthToday, int yearToday) {
    int numberOfTransactionRecords = RecordCount.transaction;
    time_t startTime, endTime;
    int i, startMonth;
    for(startMonth = 1; startMonth < monthToday; startMonth++){
        startTime = toEpochTime (1, startMonth, yearToday, 0, 0, 0);   // From: dd/mm/yyyy 00:00:00
        endTime = toEpochTime (31, startMonth, yearToday, 23, 59, 59);  // To:   dd/mm/yyyy 23:59:59
        for ( i = 0;
              i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
            if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
                // If the record is in the time range
                return startMonth;
            }
        }
    }
    return monthToday;
}

int isTimeInRange (time_t timestamp, time_t start, time_t end) {
    if ( timestamp < start )
        return -1;  // Starting point is in the future
    else if ( timestamp > end )
        return 1;   // Endpoint is in the past
    return 0;   // The time is in this range
}

int superscanf (char *input) {
    char temp[MAX_LNG_SCREEN];
    int i, len;
#ifdef __linux__
    __fpurge(stdin);
#else
    fseek (stdin, 0, SEEK_END);
#endif
    fgets (temp, sizeof (temp), stdin);
    if ( temp[0] == '\n' ) {
        return 0;
    } else {
        i = 0;
        while ( temp[i] != '\n' ) {
            input[i] = temp[i];
            i++;
        }
        input[i] = '\0';
        return 1;
    }
}

double min (double a, double b) {
    if ( a > b )
        return b;
    return a;
}

double max (double a, double b) {
    if ( a > b )
        return a;
    return b;
}
