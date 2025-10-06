// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"

/*-----------------------------------------------------------------------------
Declare all the global variables here*/
const char *monthName[12] = {"January", "February", "March", "April", "May", "June", "July", "August", "September",
                             "October", "November", "December"};

void oneDayReport (int date, int month, int year) {
    int numberOfTransactionRecords = RecordCount.transaction;
    int numberOfCategoryRecords = RecordCount.category;

    time_t startTime = toEpochTime (date, month, year, 0, 0, 0);   // From: dd/mm/yyyy 00:00:00
    time_t endTime = toEpochTime (date, month, year, 23, 59, 59);  // To:   dd/mm/yyyy 23:59:59
    for (int i = 0; i < numberOfCategoryRecords; i++ ) {
        strcpy (RevenueByCategory[i].categoryName, Category[i].name);
        RevenueByCategory[i].totalPrice = 0;
        RevenueByCategory[i].totalProfit = 0;
    }
    for (int i = 0;
          i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
        if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
            // If the record is in the time range
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalPrice += Transaction[i].inventoryPrice;
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalProfit += Transaction[i].inventoryProfit;
        }
    }
}

void multipleDayReport (int fromDate, int fromMonth, int fromYear, int toDate, int toMonth, int toYear) {
    int numberOfTransactionRecords = RecordCount.transaction;
    int numberOfCategoryRecords = RecordCount.category;
    time_t startTime = toEpochTime (fromDate, fromMonth, fromYear, 0, 0, 0);   // From: dd/mm/yyyy 00:00:00
    time_t endTime = toEpochTime (toDate, toMonth, toYear, 23, 59, 59);  // To:   dd/mm/yyyy 23:59:59
    for (int i = 0; i < numberOfCategoryRecords; i++ ) {
        // Initial the values
        strcpy (RevenueByCategory[i].categoryName, Category[i].name);
        RevenueByCategory[i].totalPrice = 0;
        RevenueByCategory[i].totalProfit = 0;
    }
    for ( int i = 0;
          i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
        if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
            // If the record is in the time range
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalPrice += Transaction[i].inventoryPrice;
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalProfit += Transaction[i].inventoryProfit;
        }
    }
}

void nextnDayReport (int fromDate, int fromMonth, int fromYear, int nDay) {
    int numberOfTransactionRecords = RecordCount.transaction;
    int numberOfCategoryRecords = RecordCount.category;
    time_t startTime = toEpochTime (fromDate, fromMonth, fromYear, 0, 0, 0);         // From: dd/mm/yyyy 00:00:00
    time_t endTime = toEpochTime (fromDate + nDay, fromMonth, fromYear, 23, 59, 59);  // To:   dd/mm/yyyy 23:59:59
    for ( int i = 0; i < numberOfCategoryRecords; i++ ) {
        // Initial the values
        strcpy (RevenueByCategory[i].categoryName, Category[i].name);
        RevenueByCategory[i].totalPrice = 0;
        RevenueByCategory[i].totalProfit = 0;
    }
    for ( int i = 0;
          i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
        if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
            // If the record is in the time range
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalPrice += Transaction[i].inventoryPrice;
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalProfit += Transaction[i].inventoryProfit;
        }
    }
}

void nextnMonthReport (int fromDate, int fromMonth, int fromYear, int nMonth) {
    int numberOfTransactionRecords = RecordCount.transaction;
    int numberOfCategoryRecords = RecordCount.category;

    time_t startTime = toEpochTime (fromDate, fromMonth, fromYear, 0, 0, 0);            // From: dd/mm/yyyy 00:00:00
    time_t endTime = toEpochTime (fromDate, fromMonth + nMonth, fromYear, 23, 59, 59);   // To:   dd/mm/yyyy 23:59:59
    for ( int i = 0; i < numberOfCategoryRecords; i++ ) {
        // Initial the values
        strcpy (RevenueByCategory[i].categoryName, Category[i].name);
        RevenueByCategory[i].totalPrice = 0;
        RevenueByCategory[i].totalProfit = 0;
    }
    for ( int i = 0;
          i < numberOfTransactionRecords && isTimeInRange (Transaction[i].timestamp, startTime, endTime) <= 0; i++ ) {
        if ( isTimeInRange (Transaction[i].timestamp, startTime, endTime) == 0 ) {
            // If the record is in the time range
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalPrice += Transaction[i].inventoryPrice;
            RevenueByCategory[Transaction[i].inventoryCategoryId].totalProfit += Transaction[i].inventoryProfit;
        }
    }
}


void monthlyReport (unsigned int year) {
    int numberOfPurchaseRecords = RecordCount.purchase;
    int numberOfMonth = 12;
    time_t startTime;
    time_t endTime;
    int monthIndex;
    for ( int i = 0; i < numberOfMonth; i++ ) {
        // Initial the values
        strcpy (RevenueByMonth[i].monthName, monthName[i]);
        RevenueByMonth[i].totalPrice = 0;
        RevenueByMonth[i].totalProfit = 0;
    }
    for ( int i = 0; i < 12; i++ ) {
        startTime = toEpochTime (1, i + 1, year, 0, 0, 0);            // From: 01/01/yyyy 00:00:00
        endTime = toEpochTime (31, i + 1, year, 23, 59, 59);   // To:   31/12/yyyy 23:59:59
        for ( int j = 0; j < numberOfPurchaseRecords; j++ ) {
            if ( isTimeInRange (Purchase[j].timestamp, startTime, endTime) == 0 ) {
                // If the record is in the time range
                monthIndex = i;
                RevenueByMonth[monthIndex].totalPrice += Purchase[j].totalPrice;
                RevenueByMonth[monthIndex].totalProfit += Purchase[j].totalProfit;
            }
        }
    }
}

// Auto alpha adjusting by choosing Least Sum Square Error
void tomorrowSaleForecast () {
    // Setting
    int nDayRollback = 7;    // Maximum number of day that will be sampling
    double alpha;    // A weight of forecasting
    // Getting time now & convert to the format of dd/mm/yyyy
    int dateToday, monthToday, yearToday;
    time_t epochTimeNow = time (NULL);
    toDateMonthYear (epochTimeNow, &dateToday, &monthToday, &yearToday);
    // Getting the real rolling days that can be rolled
    nDayRollback = getProperTimeRollingInDay (dateToday, monthToday, yearToday, nDayRollback);

    int dateRollbacked, monthRollbacked, yearRollbacked;
    time_t timeRollbacked = nDayRollbackToDateMonthYear (dateToday, monthToday, yearToday, nDayRollback);
    toDateMonthYear (timeRollbacked, &dateRollbacked, &monthRollbacked, &yearRollbacked);
    int numberOfCategoryRecords = RecordCount.category;
    int i, j, datePassed;
    long double pastTotalPrice, pastTotalProfit, pastForecastTotalPrice, pastForecastTotalProfit;
    long double sumSquareError, minSumSquareError;
    // Initialing
    for ( i = 0; i < numberOfCategoryRecords; i++ )
        strcpy (SaleForecastByCategory[i].categoryName, Category[i].name);
    for ( i = 0; i < numberOfCategoryRecords; i++ ) { // For each category
        datePassed = 0;
        sumSquareError = 0;
        minSumSquareError = 3.402823e+38;
        for ( int iter = 1; iter <= 100; iter++ ) {
            alpha = iter / 100.0;
            while ( datePassed < nDayRollback + 1 +
                                 1 ) {    // + 1 means `today also be used as sampling` & + 1 means `tomorrow` (forecasting)
                oneDayReport (dateRollbacked + datePassed, monthRollbacked, yearRollbacked);
                if ( datePassed == 0 ) {    // First time, assign the initial values
                    SaleForecastByCategory[i].totalPrice = RevenueByCategory[i].totalPrice;
                    SaleForecastByCategory[i].totalProfit = RevenueByCategory[i].totalProfit;
                } else {
                    // Revenue Forecasting
                    SaleForecastByCategory[i].totalPrice =
                            pastForecastTotalPrice + (alpha * (pastTotalPrice - pastForecastTotalPrice));
                    // Profit Forecasting
                    SaleForecastByCategory[i].totalProfit =
                            pastForecastTotalProfit + (alpha * (pastTotalProfit - pastForecastTotalProfit));
                }
                // Find Sum of Squared Error (From `start date` to `today`)
                if ( datePassed <= nDayRollback ) {
                    sumSquareError += pow (SaleForecastByCategory[i].totalPrice - RevenueByCategory[i].totalPrice, 2);
                    sumSquareError += pow (SaleForecastByCategory[i].totalProfit - RevenueByCategory[i].totalProfit, 2);
                }
                // Store past value to use in the next loop
                pastTotalPrice = RevenueByCategory[i].totalPrice;
                pastTotalProfit = RevenueByCategory[i].totalProfit;
                pastForecastTotalPrice = SaleForecastByCategory[i].totalPrice;
                pastForecastTotalProfit = SaleForecastByCategory[i].totalProfit;
                // Next day
                datePassed++;
            }
            if ( sumSquareError < minSumSquareError ) {
                minSumSquareError = sumSquareError;
                SaleForecastByCategoryTemp = SaleForecastByCategory[i];
            }
        }
        SaleForecastByCategory[i] = SaleForecastByCategoryTemp;
    }
}

void nextMonthSaleForecast () {
    double alpha;    // A weight of forecasting
    // Getting time now & convert to the format of dd/mm/yyyy
    int dateToday, monthToday, yearToday;
    time_t epochTimeNow = time (NULL);
    toDateMonthYear (epochTimeNow, &dateToday, &monthToday, &yearToday);
    int numberOfMonths = 12;
    int i, j, monthPassed;
    double pastTotalPrice, pastTotalProfit, pastForecastTotalPrice, pastForecastTotalProfit;
    long double sumSquareError, minSumSquareError;
    // Initialing
    strcpy (SaleForecastByMonth.monthName, monthName[monthToday]);
    monthlyReport (yearToday);
    i = getProperTimeStartInMonth (monthToday, yearToday) - 1; // - 1 because, the index of RevenueByMonth is start at 0
    for ( int iter = 1; iter <= 100; iter++ ) {
        alpha = iter / 100.0;
        sumSquareError = 0;
        minSumSquareError = 3.402823e+38;
        monthPassed = 0;
        for ( int i = 0; i < monthToday +
                         1; i++ ) { // means `this month also be used as sampling` & + 1 means `next month` (forecasting)
            if ( monthPassed == 0 ) {    // First time, assign the initial values
                SaleForecastByMonth.totalPrice = RevenueByMonth[i].totalPrice;
                SaleForecastByMonth.totalProfit = RevenueByMonth[i].totalProfit;
            } else {
                // Revenue Forecasting
                SaleForecastByMonth.totalPrice =
                        pastForecastTotalPrice + (alpha * (pastTotalPrice - pastForecastTotalPrice));
                // Profit Forecasting
                SaleForecastByMonth.totalProfit =
                        pastForecastTotalProfit + (alpha * (pastTotalProfit - pastForecastTotalProfit));
            }
            // Find Sum of Squared Error (From `January` to `Current month`)
            if ( i <= monthToday - 1 ) {
                sumSquareError += pow (SaleForecastByMonth.totalPrice - RevenueByMonth[i].totalPrice, 2);
                sumSquareError += pow (SaleForecastByMonth.totalProfit - RevenueByMonth[i].totalProfit, 2);
            }
            // Store past value to use in the next loop
            pastTotalPrice = RevenueByMonth[i].totalPrice;
            pastTotalProfit = RevenueByMonth[i].totalProfit;
            pastForecastTotalPrice = SaleForecastByMonth.totalPrice;
            pastForecastTotalProfit = SaleForecastByMonth.totalProfit;
            // Next month
            monthPassed++;
        }
        if ( sumSquareError < minSumSquareError ) {
            minSumSquareError = sumSquareError;
            SaleForecastByMonthTemp = SaleForecastByMonth;
        }
    }
    SaleForecastByMonth = SaleForecastByMonthTemp;
}

void personnelSaleReport (unsigned int year) {
    int numberOfPersonnelRecords = RecordCount.personnel;
    int numberOfPurchaseRecords = RecordCount.purchase;
    time_t startTime = toEpochTime (1, 1, year, 0, 0, 0);            // From: 01/01/yyyy 00:00:00
    time_t endTime = toEpochTime (31, 12, year, 23, 59, 59);   // To:   31/12/yyyy 23:59:59
    int i, j;
    for ( i = 0; i < numberOfPersonnelRecords; i++ ) {
        // Initializing the information of each record
        strcpy (RevenueByPersonnel[i].id, Personnel[i].id);
        strcpy (RevenueByPersonnel[i].firstname, Personnel[i].firstname);
        strcpy (RevenueByPersonnel[i].lastname, Personnel[i].lastname);
        RevenueByPersonnel[i].totalPrice = 0;
        RevenueByPersonnel[i].totalProfit = 0;
        for ( j = 0;
              j < numberOfPurchaseRecords && isTimeInRange (Purchase[j].timestamp, startTime, endTime) <= 0; j++ ) {
            if ( strcmp (Personnel[i].id, Purchase[j].personnelId) == 0 &&
                 isTimeInRange (Purchase[j].timestamp, startTime, endTime) == 0 ) {
                RevenueByPersonnel[i].totalPrice += Purchase[j].totalPrice;
                RevenueByPersonnel[i].totalProfit += Purchase[j].totalProfit;
            }
        }
    }
}

int checkErrorIn = 0; //State for Error.
void reportSwitchHub () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Report of Sales");
    bannerBlankBorder ();
    bannerFullBorder ();

    for ( int i = 0; i < 11; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("What do you want to do ?");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("1. View one day report");
    bannerBlankBorderTextCen ("2. View monthly report");
    bannerBlankBorderTextCen ("3. View personnel sale report");
    bannerBlankBorderTextCen ("4. View multiple day report");
    for ( int i = 0; i < 12; i++ )
        bannerBlankBorder ();
    if ( checkErrorIn )
        bannerBlankBorderTextCen ("Invalid input. Please try again !!!!");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    /*-----User input------*/
    bannerUserInput ();
    char UserIn;
    scanf (" %c", &UserIn);
    switch ( toupper (UserIn)) {
        case ('1'):
            checkErrorIn = 0;
            OneDayReportInputProcess ();
            break;
        case ('2'):
            checkErrorIn = 0;
            MonthlyReportInputProcess ();
            break;
        case ('3'):
            checkErrorIn = 0;
            PersonnelSaleReportInputProcess ();
            break;
        case ('4'):
            checkErrorIn = 0;
            MultipleDayReportInputProcess ();
            break;
        case ('B'):
            switchHub ();
        case ('Q'):
            terminate ();
        default:
            checkErrorIn = 1;
            reportSwitchHub ();
    }
}

void OneDayReportInputProcess () {
    /*-----Initial interface-----*/
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("One Day Report");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 15; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter date...");
    bannerBlankBorderTextCen ("Example --> dd/mm/yyyy");
    for ( int i = 0; i < 14; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    int dateIN, monthIN, yearIN;
    char swInput[5];
    // Input
    bannerUserInput ();
    scanf (" %d/%d/%d", &dateIN, &monthIN, &yearIN);
    sprintf (swInput, "%d", dateIN);
    // Process
    oneDayReport (dateIN, monthIN, yearIN);
    OneDayReportInterface ();
}

void displayOneDayReport (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.category / 32) + 1;
    bannerFullBorder ();
    printf (":: %-68s |             Revenue            |              Profit            ::\n", "Category Name");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.category; ++i )
            printf (":: %-68s | %30.2lf | %30.2lf ::\n", RevenueByCategory[i].categoryName,
                    RevenueByCategory[i].totalPrice, RevenueByCategory[i].totalProfit);
        for ( int i = 0; i < 32 - (RecordCount.category % 32); ++i )
            printf ("::                                                                      |                                |                                ::\n");
    } else
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i )
            printf (":: %-68s | %30.2lf | %30.2lf ::\n", RevenueByCategory[i].categoryName,
                    RevenueByCategory[i].totalPrice, RevenueByCategory[i].totalProfit);
    bannerBlankBorderTextCen ("'N' to enter new date | Enter Page(e.g. 1, 2, 3) | 'B' to Check Report Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void OneDayReportInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayOneDayReport (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            reportSwitchHub ();
        } else if ((handling == 'N') || (handling == 'n')) {
            OneDayReportInputProcess ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.category / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayOneDayReport (pageIn);
            } else {
                displayOneDayReport (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayOneDayReport (pageIn);
            printf ("Oops! Input is valided, Please enter correctly: ");
        }
    }
}

/*---------------------------------------------------------------Monthly Report----------------------------------------------------------------------*/
void MonthlyReportInputProcess () {
    /*-----Initial interface-----*/
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Monthly Report");
    bannerFullBorder ();
    for ( int i = 0; i < 16; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter year...");
    bannerBlankBorderTextCen ("Example --> 2017");
    for ( int i = 0; i < 16; ++i )
        bannerBlankBorder ();
    bannerFullBorder ();
    unsigned int year;
    // Input
    bannerUserInput ();
    scanf ("%u", &year);
    // Process
    monthlyReport (year);
    MonthlyReportInterface ();
}

void displayMonthlyReport () {
    screenClear ();
    bannerFullBorder ();
    printf (":: %-68s |             Revenue            |              Profit            ::\n", "Month");
    bannerFullBorder ();
    for ( int i = 0; i < 12; ++i )
        printf (":: %-68s | %30.2lf | %30.2lf ::\n", RevenueByMonth[i].monthName, RevenueByMonth[i].totalPrice,
                RevenueByMonth[i].totalProfit);
    for ( int i = 0; i < 21; ++i )
        printf ("::                                                                      |                                |                                ::\n");
    bannerBlankBorderTextCen ("'N' to enter year again  |      ALTERNATE RESPONSE      |  'B' to Check Report Menu ");
    bannerFullBorder ();
    bannerUserInput ();
}

void MonthlyReportInterface () {
    screenClear ();
    char handling;
    displayMonthlyReport ();
    for ( int i = 0; i >= 0; ++i ) {
        //printf (">>> ");
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            reportSwitchHub ();
        } else if ((handling == 'N') || (handling == 'n')) {
            MonthlyReportInputProcess ();
        } else {
            displayMonthlyReport ();
            printf ("Oops! Input is valid, Please enter correctly: ");
        }
    }
}

/*---------------------------------------------------------------Personnel Report----------------------------------------------------------------------*/
void PersonnelSaleReportInputProcess () {
    /*-----Initial interface-----*/
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Personeel Sale Report");
    bannerFullBorder ();
    for ( int i = 0; i < 16; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter year...");
    bannerBlankBorderTextCen ("Example --> 2017");
    for ( int i = 0; i < 16; ++i )
        bannerBlankBorder ();
    bannerFullBorder ();
    unsigned int year;
    // Input
    bannerUserInput ();
    scanf ("%u", &year);
    // Process
    personnelSaleReport (year);
    PersonnelSaleReportInterface ();
}

void displayPersonnelSaleReport (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.personnel / 32) + 1;
    bannerFullBorder ();
    printf (":: %-14s | %-35s | %-35s | %19s | %19s ::\n", "Personnel ID", "Firstname", "Lastname", "Revenue",
            "Profit");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.personnel; ++i ) {
            printf (":: %-14s | %-35s | %-35s | %19.2lf | %19.2lf ::\n", RevenueByPersonnel[i].id,
                    RevenueByPersonnel[i].firstname, RevenueByPersonnel[i].lastname, RevenueByPersonnel[i].totalPrice,
                    RevenueByPersonnel[i].totalProfit);
        }
        for ( int i = 0; i < 32 - (RecordCount.personnel % 32); ++i )
            printf (":: %-14s | %-35s | %-35s | %19s | %19s ::\n", "", "", "", "", "");
    } else
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i ) {
            printf (":: %-14s | %-35s | %-35s | %19.2lf | %19.2lf ::\n", RevenueByPersonnel[i].id,
                    RevenueByPersonnel[i].firstname, RevenueByPersonnel[i].lastname, RevenueByPersonnel[i].totalPrice,
                    RevenueByPersonnel[i].totalProfit);
        }
    bannerBlankBorderTextCen ("'N' to enter new year | Enter Page | 'B' to back to Check Report Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void PersonnelSaleReportInterface () {
    screenClear ();
    char handling;
    int pageIn = 1, CheckPage;
    displayPersonnelSaleReport (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            reportSwitchHub ();
        } else if ((handling == 'N') || (handling == 'n')) {
            PersonnelSaleReportInputProcess ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.category / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayPersonnelSaleReport (pageIn);
            } else {
                displayPersonnelSaleReport (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayPersonnelSaleReport (pageIn);
            printf ("Oops! Input is valid, Please enter correctly: ");
        }
    }
}

/*---------------------------------------------------------------Multiple Day Report----------------------------------------------------------------------*/
void MultipleDayReportInputProcess () {
    /*-----Initial interface-----*/
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Multiple Day Report");
    bannerFullBorder ();
    for ( int i = 0; i < 15; ++i ) {
        bannerBlankBorder ();
    }
    bannerBlankBorderTextCen ("Please enter date...(dd/mm/yyyy)");
    bannerBlankBorderTextCen ("Example: From >>> 07/03/2017");
    bannerBlankBorderTextCen ("           To >>> 14/03/2017");
    for ( int i = 0; i < 16; ++i ) {
        bannerBlankBorder ();
    }
    bannerFullBorder ();
    /*--------------------------*/
    int FdateIN, FmonthIN, FyearIN, TdateIN, TmonthIN, TyearIN;
    //Input
    printf ("From >>> ");
    scanf (" %d/%d/%d", &FdateIN, &FmonthIN, &FyearIN);
    printf ("To >>> ");
    scanf (" %d/%d/%d", &TdateIN, &TmonthIN, &TyearIN);
    //Process
    multipleDayReport (FdateIN, FmonthIN, FyearIN, TdateIN, TmonthIN, TyearIN);
    MultipleDayReportInterface ();
}

void displayMultipleDayReport (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.category / 32) + 1;
    bannerFullBorder ();
    printf (":: %-68s |             Revenue            |              Profit            ::\n", "Category Name");
    bannerFullBorder ();

    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.category; ++i ) {
            printf (":: %-68s | %30.2lf | %30.2lf ::\n", RevenueByCategory[i].categoryName,
                    RevenueByCategory[i].totalPrice, RevenueByCategory[i].totalProfit);
        }
        for ( int i = 0; i < 32 - (RecordCount.category % 32); ++i ) {
            printf ("::                                                                      |                                |                                ::\n");
        }
    } else {
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i ) {
            printf (":: %-68s | %30.2lf | %30.2lf ::\n", RevenueByCategory[i].categoryName,
                    RevenueByCategory[i].totalPrice, RevenueByCategory[i].totalProfit);
        }
    }
    bannerBlankBorderTextCen ("'N' to enter new date | Enter Page(e.g. 1, 2, 3) | 'B' to Check Report Menu |");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void MultipleDayReportInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayMultipleDayReport (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            reportSwitchHub ();
        } else if ((handling == 'N') || (handling == 'n')) {
            MultipleDayReportInputProcess ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.category / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayMultipleDayReport (pageIn);
            } else {
                displayMultipleDayReport (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayMultipleDayReport (pageIn);
            printf ("Oops! Input is valided, Please enter correctly: ");
        }
    }
}

/*---------------------------------------------------------------forecasting----------------------------------------------------------------------*/
int ErrorINput = 0;

void forecastSwitchHub () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Sale Forecasting");
    bannerBlankBorder ();
    bannerFullBorder ();
    if ( ErrorINput ) {
        for ( int i = 0; i < 3; ++i ) {
            bannerBlankBorder ();
        }
        bannerBlankBorderTextCen ("Invalid input. Please try again !!!!");
        for ( int i = 0; i < 9; ++i ) {
            bannerBlankBorder ();
        }
    } else {
        for ( int i = 0; i < 13; ++i ) {
            bannerBlankBorder ();
        }
    }
    bannerBlankBorderTextCen ("Choose a forecasting");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("1. Tomorrow forecasting");
    bannerBlankBorderTextCen ("2. Next month forecasting");
    for ( int i = 0; i < 14; i++ ) {
        bannerBlankBorder ();
    }
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();

    /*-----User input------*/
    char UserIn;
    bannerUserInput ();
    scanf (" %c", &UserIn);
    switch ( toupper (UserIn)) {
        case ('1'):
            ErrorINput = 0;
            ShowTomorrowForecasting ();
            break;

        case ('2'):
            ErrorINput = 0;
            ShowNextMonthForecasting ();
            break;

        case ('Q'):
            terminate ();
            break;

        case ('B'):
            ErrorINput = 0;
            switchHub ();
            break;

        default:
            ErrorINput = 1;
            forecastSwitchHub ();
    }
}

/*---------------------------------------------------------------Tomorrow forecasting----------------------------------------------------------------------*/
void displayTomorrowForecasting (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.category / 32) + 1;
    double different;
    char sign;
    bannerFullBorder ();
    printf (":: %39s |                   %-21s |                 %-23s | %8s ::\n", "", "TODAY", "TOMORROW", "");
    printf ("::                 %-23s |       %-12s |        %-11s |       %-12s |        %-11s |     %-4s ::\n",
            "Category", "Revenue", "Profit", "Revenue", "Profit", "%");
    //printf (":: %-68s |             Revenue            |              Profit            ::\n", "Category Name");
    bannerFullBorder ();

    if ( page == allPage ) {
        for ( int i = (page - 1) * 32; i < RecordCount.category; ++i ) {
            if ( RevenueByCategory[i].totalProfit > SaleForecastByCategory[i].totalProfit ) {
                sign = '-';
                different = ((SaleForecastByCategory[i].totalProfit - RevenueByCategory[i].totalProfit) /
                             RevenueByCategory[i].totalProfit) * 100;
            } else if ( RevenueByCategory[i].totalProfit < SaleForecastByCategory[i].totalProfit ) {
                sign = '+';
                different = ((SaleForecastByCategory[i].totalProfit - RevenueByCategory[i].totalProfit) /
                             RevenueByCategory[i].totalProfit) * 100;
            } else {
                sign = '+';
                different = 0;
            }
            printf (":: %-39s | %18.2lf | %18.2lf | %18.2lf | %18.2lf | %c%7.2lf ::\n",
                    SaleForecastByCategory[i].categoryName, RevenueByCategory[i].totalPrice,
                    RevenueByCategory[i].totalProfit, SaleForecastByCategory[i].totalPrice,
                    SaleForecastByCategory[i].totalProfit, sign, fabs (different));
        }
        for ( int i = 0; i < 32 - (RecordCount.category % 32) - 2; ++i ) {
            printf (":: %-39s | %18s | %18s | %18s | %18s | %8s ::\n", "", "", "", "", "", "");
        }
    } else {
        for ( int i = (page - 1) * 32; i < page * 32/*(34*page)*/; ++i ) {
            if ( RevenueByCategory[i].totalProfit > SaleForecastByCategory[i].totalProfit ) {
                sign = '-';
                different = ((SaleForecastByCategory[i].totalProfit - RevenueByCategory[i].totalProfit) /
                             RevenueByCategory[i].totalProfit) * 100;
            } else if ( RevenueByCategory[i].totalProfit < SaleForecastByCategory[i].totalProfit ) {
                sign = '+';
                different = ((SaleForecastByCategory[i].totalProfit - RevenueByCategory[i].totalProfit) /
                             RevenueByCategory[i].totalProfit) * 100;
            } else {
                sign = '+';
                different = 0;
            }
            printf (":: %-39s | %18.2lf | %18.2lf | %18.2lf | %18.2lf | %c%7.2lf ::\n",
                    SaleForecastByCategory[i].categoryName, RevenueByCategory[i].totalPrice,
                    RevenueByCategory[i].totalProfit, SaleForecastByCategory[i].totalPrice,
                    SaleForecastByCategory[i].totalProfit, sign, fabs (different));
        }
    }
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Enter Page(e.g. 1, 2, 3) | 'B' to Forecasting Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void ShowTomorrowForecasting () {
    time_t today = time (NULL);
    int date, month, year;
    toDateMonthYear (today, &date, &month, &year);
    int i;

    tomorrowSaleForecast (); //Execute Forecast processing.
    oneDayReport (date, month, year);

    char handling;
    int pageIn = 1, CheckPage;
    displayTomorrowForecasting (1);
    for ( i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            forecastSwitchHub ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.category / 32) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayTomorrowForecasting (pageIn);
            } else {
                displayTomorrowForecasting (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayTomorrowForecasting (pageIn);
            printf ("Oops! Input is valided, Please enter correctly: ");
        }
    }
}
/*---------------------------------------------------------------Next Month forecasting----------------------------------------------------------------------*/
void ShowNextMonthForecasting () {
    nextMonthSaleForecast ();//Execute Forecast processing.

    char handling;
    int pageIn = 1, CheckPage;
    displayNextMonthForecasting ();
    for ( int i = 0; i >= 0; ++i ) {

        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            forecastSwitchHub ();
        } else {
            displayNextMonthForecasting (pageIn);
            printf ("Oops! Input is valided, Please enter correctly: ");
        }
    }
}

void displayNextMonthForecasting () {
    screenClear ();
    time_t today = time (NULL);
    int date, month, year;
    toDateMonthYear (today, &date, &month, &year);
    char thisMonthName[10];
    strcpy (thisMonthName, monthName[month - 1]);
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Next Month Forecasting");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 11; ++i )
        bannerBlankBorder ();
    printf (":: %67s %-10s %-55d ::\n", "This month:", thisMonthName, year);
    printf (":: %67s %-66.2lf ::\n", "- Revenue:", RevenueByMonth[month - 1].totalPrice);
    printf (":: %67s %-66.2lf ::\n", "- Profit:", RevenueByMonth[month - 1].totalProfit);
    bannerBlankBorder ();
    printf (":: %67s %-10s %-55d ::\n", "Next month:", SaleForecastByMonth.monthName, year);
    printf (":: %67s %-66.2lf ::\n", "- Revenue:", SaleForecastByMonth.totalPrice);
    printf (":: %67s %-66.2lf ::\n", "- Profit:", SaleForecastByMonth.totalProfit);
    for ( int i = 0; i < 13; ++i )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char sw;
    scanf (" %c", &sw);
    switch ( toupper (sw)) {
        case 'Q':
            switchHub ();
            break;
        case 'B':
            forecastSwitchHub ();
            break;
        default:
            displayNextMonthForecasting ();
    }
}
