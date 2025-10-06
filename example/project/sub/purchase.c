// Welcome to the program. The declaration of the functions and the library used is in .h file
#include "../main.h"

int
purchaseSelectById (unsigned int id, double *totalPrice, double *totalDiscount, double *totalProfit, char *customerId,
                    char *personnelId, time_t *timestamp) {
    int numberOfRecords;    // Number of the records in a table
    numberOfRecords = RecordCount.purchase;
    for ( int i = 0; i < numberOfRecords; i++ ) {
        if ( Purchase[i].id == id ) {
            // Return all values back by reference
            *totalPrice = Purchase[i].totalPrice;
            *totalDiscount = Purchase[i].totalDiscount;
            *totalProfit = Purchase[i].totalProfit;
            strcpy (customerId, Purchase[i].customerId);
            strcpy (personnelId, Purchase[i].personnelId);
            *timestamp = Purchase[i].timestamp;
            return 1;   // Found a record
        }
    }
    return 0;           // Not found the given `id` in the records
}

void purchaseInsert (double totalPrice, double totalDiscount, double totalProfit, char *customerId, char *personnelId) {
    int tailIndex = RecordCount.purchase;
    Purchase[tailIndex].id = tailIndex;    // Auto-increment
    Purchase[tailIndex].totalPrice = totalPrice;
    Purchase[tailIndex].totalDiscount = totalDiscount;
    Purchase[tailIndex].totalProfit = totalProfit;
    strcpy (Purchase[tailIndex].customerId, customerId);
    strcpy (Purchase[tailIndex].personnelId, personnelId);
    Purchase[tailIndex].timestamp = time (NULL);     // Current time as time_t (Epoch format)
    RecordCount.purchase++;    // Update the amount of records
    purchaseFileWrite ();       // Save to a Database file
}
