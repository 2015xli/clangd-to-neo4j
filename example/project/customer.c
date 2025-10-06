// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "main.h"
#include "string.h"
#include "ctype.h"

void customerSwitchHub () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Customer Management");
    bannerBlankBorder ();
    bannerFullBorder ();
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("What do you want to do ?");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("1. Preview customer database");
    bannerBlankBorderTextCen ("2. Create new customer ID");
    bannerBlankBorderTextCen ("3. Delete customer metadata from the database");
    bannerBlankBorderTextCen ("4. Update existed customer");
    for ( int i = 0; i < 14; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to quit  |      ALTERNATE RESPONSE      |  Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char flag;
    scanf (" %c", &flag);
    switch ( toupper (flag)) {
        case ('1'):
            customerSelectInterface ();
            break;
        case ('2'):
            customerInsertInterface ();
            break;
        case ('3'):
            customerDeleteInterface ();
            break;
        case ('4'):
            customerUpdateInterface ();
            break;
        case ('B'):
            switchHub ();
        case ('Q'):
            terminate ();
        default:
            customerSwitchHub ();
            return;
    }
}

void customerInsertInterface () {
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Customer Database");
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Create new Customer ID");
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Insert in form");
    bannerBlankBorderTextCen ("Form: ID");
    bannerBlankBorderTextCen ("Firstname");
    bannerBlankBorderTextCen ("Lastname");
    bannerBlankBorderTextCen ("Gender(M/F)");
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Ex: 1234567891012");
    bannerBlankBorderTextCen ("Prayut");
    bannerBlankBorderTextCen ("Chun-O-Char");
    bannerBlankBorderTextCen ("M");
    bannerBlankBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextCen ("Insert CustomerID Below");
    for ( int i = 0; i < 16; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], name[MAX_LNG_TEXT], lastname[MAX_LNG_TEXT], gender, buffer[140], checker, bufferHead[140];
    int genderCheck;
    sprintf (bufferHead, "%-20s|%-50s|%-50s|%s", "ID", "Firstname", "Lastname", "Gender");
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            customerSwitchHub ();
            break;
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
            break;
        } else { //------------------After Input ID--------------------
            screenClear ();
            sprintf (buffer, "%-20s->", id);
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Customer Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please Type Customer Firstname...");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------FirstName--------------------------
            scanf (" %[^\n]", name);
            sprintf (buffer, "%-20s %-50s->", id, name);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Customer Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please Type Customer Lastname...");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------LastName--------------------------
            scanf (" %[^\n]", lastname);
            sprintf (buffer, "%-20s %-50s %-50s->", id, name, lastname);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Customer Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 27; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Please Type Customer Gender (M/F)...");
            bannerFullBorder ();
            bannerUserInput ();
            //---------------------Gender--------------------------
            scanf (" %c", &gender);
            screenClear ();
            bannerFullBorder ();
            bannerBlankBorderTextCen ("Customer Database");
            bannerFullBorder ();
            bannerBlankBorder ();
            bannerBlankBorderTextLeft (bufferHead);
            bannerFullBorderSection ();
            bannerBlankBorder ();
            bannerBlankBorder ();
            if ( gender == 'F' || gender == 'f' )
                sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Female");
            if ( gender == 'M' || gender == 'm' )
                sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Male");
            bannerBlankBorderTextLeft (buffer);
            for ( int i = 0; i < 10; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Are you sure to Insert this customer ?");
            bannerBlankBorderTextCen ("Type 'Y' to Yes || 'N' to No");
            for ( int i = 0; i < 15; i++ )
                bannerBlankBorder ();
            bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
            bannerFullBorder ();
            bannerUserInput ();
            scanf (" %c", &checker);
            if ( checker == 'y' || checker == 'Y' ) {
                if ( customerInsert (id, name, lastname, toupper (gender))) {
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Customer Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();

                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    if ( gender == 'F' || gender == 'f' )
                        sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Female");
                    if ( gender == 'M' || gender == 'm' )
                        sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Male");
                    bannerBlankBorderTextLeft (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    for ( int i = 0; i < 8; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert Success");
                    bannerBlankBorderTextCen ("_____________________");
                    bannerBlankBorderTextCen ("Insert Next Customer Or Type 'B' to Back");
                    for ( int i = 0; i < 12; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    sprintf (buffer, "ID: %s", id);
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Customer Database");
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Insert Customer");
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert not Successful !");
                    bannerBlankBorderTextCen ("Please check your customer ID");
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen (buffer);
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("was a duplicate");
                    bannerBlankBorderTextCen ("_____________________");
                    bannerBlankBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Insert Next Customer Or Type 'B' to Back");
                    for ( int i = 0; i < 19; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                }
            } else {
                customerInsertInterface ();
            }
        }
    }
}

void displayCustomer (int page) {
    screenClear ();
    int allPage = (int) ceil (RecordCount.customer / 34) + 1;
    char NewGender[7];
    bannerFullBorder ();
    printf (":: %-20s | %-35s | %-35s | %-8s | %10s | %11s ::\n", "Customer ID", "Firstname", "Lastname", "Gender",
            "Point", "Total Buy");
    bannerFullBorder ();
    if ( page == allPage ) {
        for ( int i = (page - 1) * 34; i < RecordCount.customer; ++i ) {
            if ( Customer[i].gender == 'F' )
                strcpy (NewGender, "Female");
            else
                strcpy (NewGender, "Male");
            printf (":: %-20s | %-35s | %-35s | %-8s | %10.2lf | %11.2lf ::\n", Customer[i].id, Customer[i].firstname,
                    Customer[i].lastname, NewGender, Customer[i].point,
                    Customer[i].totalBuy);
        }
        for ( int i = 0; i < 34 - 2 - (RecordCount.customer % 34); ++i )
            printf (":: %-20s | %-35s | %-35s | %-8s | %10s | %11s ::\n", "", "", "", "", "", "");
    } else {
        for ( int i = (page - 1) * 34; i < page * 34 - 2/*(34*page)*/; ++i ) {
            if ( Customer[i].gender == 'F' )
                strcpy (NewGender, "Female");
            else
                strcpy (NewGender, "Male");
            printf (":: %-20s | %-35s | %-35s | %-8s | %10.2lf | %11.2lf ::\n", Customer[i].id, Customer[i].firstname,
                    Customer[i].lastname, NewGender, Customer[i].point,
                    Customer[i].totalBuy);
        }
    }

    bannerBlankBorderTextCen ("Enter Page/Enter 'B' to back to Customer Menu");
    printf ("::                                                       <<  <  ( Page %d of %d ) > >>                                                      ::\n",
            page, allPage);
    bannerFullBorder ();
    bannerUserInput ();
}

void customerSelectInterface () {
    char handling;
    int pageIn = 1, CheckPage;
    displayCustomer (1);
    for ( int i = 0; i >= 0; ++i ) {
        scanf (" %c", &handling);
        if ((handling == 'B') || (handling == 'b')) {
            screenClear ();
            customerSwitchHub ();
        } else if ( isdigit (handling)) {
            CheckPage = (int) handling - 48;
            if ((CheckPage <= ((int) ceil (RecordCount.customer / 34) + 1)) && (CheckPage >= 1)) {
                pageIn = (int) handling - 48;
                displayCustomer (pageIn);
            } else {
                displayCustomer (pageIn);
                printf ("Oops! Page not found, Please enter correct page: ");
            }
        } else {
            displayCustomer (pageIn);
            printf ("Oops! Input Error, Please enter correctly: ");
        }
    }
}

void customerDeleteInterface () {
    char bufferHead[140];
    sprintf (bufferHead, "%-15s|%-40s|%-40s|%-10s|%-10s|%-10s", "ID", "Firstname", "Lastname", "Gender", "Point",
             "Totalbuy");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Customer Database");
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (bufferHead);
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    bannerBlankBorder ();
    bannerBlankBorder ();
    for ( int i = 0; i < 26; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      Please Type CustomerID...     |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], name[MAX_LNG_TEXT], lastname[MAX_LNG_TEXT], gender, buffer[140], flag;
    double point, totalbuy;
    while (1) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            customerSwitchHub ();
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
        } else {
            if ( customerSelectById (id, name, lastname, &gender, &point, &totalbuy)) {
                screenClear ();
                if ( gender == 'F' || gender == 'f' )
                    sprintf (buffer, "%-15s %-40s %-40s %-10s %-10.2lf %-10.2lf", id, name, lastname, "Female", point,
                             totalbuy);
                if ( gender == 'M' || gender == 'm' )
                    sprintf (buffer, "%-15s %-40s %-40s %-10s %-10.2lf %-10.2lf", id, name, lastname, "Male", point,
                             totalbuy);
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Customer Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Are you sure to delete ?");
                bannerBlankBorderTextCen ("Type 'Y' to comfirm || Type 'N' to Discard");
                for ( int i = 0; i < 16; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
                scanf (" %c", &flag);
                if ( flag == 'Y' || flag == 'y' ) {
                    customerDelete (id);
                    screenClear ();
                    bannerFullBorder ();
                    bannerBlankBorderTextCen ("Customer Database");
                    bannerFullBorder ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft (bufferHead);
                    bannerFullBorderSection ();
                    bannerBlankBorder ();
                    bannerBlankBorderTextLeft ("->");
                    for ( int i = 0; i < 10; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Delete Success");
                    bannerBlankBorderTextCen ("Type Next CustomerID Or Type 'B' to Back");
                    for ( int i = 0; i < 16; i++ )
                        bannerBlankBorder ();
                    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                    bannerFullBorder ();
                    bannerUserInput ();
                } else {
                    screenClear ();
                    customerDeleteInterface ();
                }
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Customer Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 11; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("CustomerID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next CustomerID Or Type 'B' to Back");

                for ( int i = 0; i < 15; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }
        }
    }
}

void customerUpdateInterface () {
    char bufferHead[140];
    sprintf (bufferHead, "%-20s|%-50s|%-50s|%s", "ID", "Firstname", "Lastname", "Gender");
    screenClear ();
    bannerFullBorder ();
    bannerBlankBorderTextCen ("Customer Database");
    bannerFullBorder ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft (bufferHead);
    bannerFullBorderSection ();
    bannerBlankBorder ();
    bannerBlankBorderTextLeft ("->");
    for ( int i = 0; i < 10; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Please enter a Customer ID");
    for ( int i = 0; i < 17; i++ )
        bannerBlankBorder ();
    bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
    bannerFullBorder ();
    bannerUserInput ();
    char id[MAX_LNG_ID], name[MAX_LNG_TEXT], lastname[MAX_LNG_TEXT], gender, buffer[140], flag[MAX_LNG_TEXT], genderChanged[2];
    double point, totalbuy;
    while ( 1 ) {
        scanf ("%s", id);
        if ( strcmp (id, "B") == 0 || strcmp (id, "b") == 0 ) {
            customerSwitchHub ();
        } else if ( strcmp (id, "Q") == 0 || strcmp (id, "q") == 0 ) {
            terminate ();
        } else {
            if ( customerSelectById (id, name, lastname, &gender, &point, &totalbuy)) {
                screenClear ();
                if ( gender == 'F' || gender == 'f' )
                    sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Female");
                if ( gender == 'M' || gender == 'm' )
                    sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Male");
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Customer Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorderTextCen (" ");
                for ( int i = 0; i < 27; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type another name to change customer name... | Press Enter to set by default");
                bannerFullBorder ();
                bannerUserInput ();
                printf ("Default Firstname: (%s) >>> ", name);
                if ( superscanf (flag) != 0 )
                    customerUpdateFirstname (id, flag);
                printf ("Default Lastname: (%s) >>> ", lastname);
                if ( superscanf (flag) != 0 )
                    customerUpdateLastname (id, flag);
                printf ("Default Gender: (%c) >>> ", gender);
                if ( superscanf (genderChanged) != 0 )
                    customerUpdateGender (id, toupper (genderChanged[0]));
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Customer Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                customerSelectById (id, name, lastname, &gender, &point, &totalbuy);
                if ( gender == 'F' || gender == 'f' )
                    sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Female");
                if ( gender == 'M' || gender == 'm' )
                    sprintf (buffer, "%-20s %-50s %-50s %s", id, name, lastname, "Male");
                bannerBlankBorderTextLeft (buffer);
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Customer has been updated");
                bannerBlankBorderTextCen ("Type Next CustomerID to Update Or Type 'B' to Back");
                for ( int i = 0; i < 14; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            } else {
                screenClear ();
                bannerFullBorder ();
                bannerBlankBorderTextCen ("Customer Database");
                bannerFullBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft (bufferHead);
                bannerFullBorderSection ();
                bannerBlankBorder ();
                bannerBlankBorderTextLeft ("->");
                for ( int i = 0; i < 10; i++ )
                    bannerBlankBorder ();
                bannerBlankBorder ();
                bannerBlankBorderTextCen ("CustomerID dosen't exist.");
                bannerBlankBorderTextCen ("Type Next CustomerID Or Type 'B' to Back");
                for ( int i = 0; i < 15; i++ )
                    bannerBlankBorder ();
                bannerBlankBorderTextCen ("Type 'Q' to stop   |      ALTERNATE RESPONSE      |   Type 'B' to back");
                bannerFullBorder ();
                bannerUserInput ();
            }
        }
    }
}

int customerSelectById (char *id, char *firstname, char *lastname, char *gender, double *point, double *totalBuy) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            // Return all values back by reference
            strcpy (firstname, Customer[i].firstname);
            strcpy (lastname, Customer[i].lastname);
            *gender = Customer[i].gender;
            *point = Customer[i].point;
            *totalBuy = Customer[i].totalBuy;
            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}

int customerInsert (char *id, char *firstname, char *lastname, char gender) {
    int tailIndex = RecordCount.customer;
    // To comfirm that `id` is unique
    for ( int i = 0; i < tailIndex; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 )
            return 0;   // Error: Customer ID already exists
    }
    strcpy (Customer[tailIndex].id, id);
    strcpy (Customer[tailIndex].firstname, firstname);
    strcpy (Customer[tailIndex].lastname, lastname);
    Customer[tailIndex].gender = gender;
    Customer[tailIndex].point = 0;          // Initail value
    Customer[tailIndex].totalBuy = 0;       // Initail value
    RecordCount.customer++;    // Update the amount of records
    customerFileWrite ();       // Save to a Database file
    return 1;                  // Operation Success
}

int customerUpdateFirstname (char *id, char *firstname) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            strcpy (Customer[i].firstname, firstname);
            customerFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int customerUpdateLastname (char *id, char *lastname) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            strcpy (Customer[i].lastname, lastname);
            customerFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int customerUpdateGender (char *id, char gender) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            Customer[i].gender = gender;
            customerFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int customerUpdatePoint (char *id, double point) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            Customer[i].point = point;
            customerFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int customerUpdatetotalBuy (char *id, double totalBuy) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            Customer[i].totalBuy = totalBuy;
            customerFileWrite ();    // Save to a Database file
            return 1;               // Record successfully updated
        }
    }
    return 0;   // Not found the given `id` in the records
}

int customerDelete (char *id) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.customer;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( strcmp (Customer[i].id, id) == 0 ) {
            while ( i < numberOfRecords - 1 ) {
                Customer[i] = Customer[i + 1];
                i++;
            }
            RecordCount.customer--;    // Update the amount of records
            customerFileWrite ();       // Save to a Database file
            return 1;                  // Record successfully deleted
        }
    }
    return 0;   // Not found the given `id` in the records
}
