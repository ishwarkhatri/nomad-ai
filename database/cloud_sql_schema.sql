-- Cloud SQL PostgreSQL Schema for Nomad-AI
-- Run this on your existing Cloud SQL instance

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create itineraries table
CREATE TABLE IF NOT EXISTS itineraries (
    itinerary_id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    trip_name VARCHAR(500) NOT NULL,
    origin VARCHAR(255),
    destination VARCHAR(255),
    start_date DATE,
    end_date DATE,
    itinerary_data JSONB NOT NULL,
    booking_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_booking_status CHECK (booking_status IN ('pending', 'booked', 'cancelled', 'completed'))
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_itineraries_user_id ON itineraries(user_id);
CREATE INDEX IF NOT EXISTS idx_itineraries_dates ON itineraries(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_itineraries_status ON itineraries(booking_status);
CREATE INDEX IF NOT EXISTS idx_itineraries_created_at ON itineraries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_itineraries_data_gin ON itineraries USING GIN (itinerary_data);

-- Create bookings table
CREATE TABLE IF NOT EXISTS bookings (
    booking_id SERIAL PRIMARY KEY,
    itinerary_id INTEGER REFERENCES itineraries(itinerary_id) ON DELETE CASCADE,
    booking_reference VARCHAR(100) UNIQUE NOT NULL,
    booking_type VARCHAR(50) NOT NULL,
    booking_details JSONB NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'pending',
    payment_method VARCHAR(50),
    amount_usd DECIMAL(10, 2),
    confirmation_number VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_booking_type CHECK (booking_type IN ('flight', 'hotel', 'activity', 'transport', 'event')),
    CONSTRAINT check_payment_status CHECK (payment_status IN ('pending', 'processing', 'completed', 'failed', 'refunded'))
);

-- Create indexes for bookings
CREATE INDEX IF NOT EXISTS idx_bookings_itinerary_id ON bookings(itinerary_id);
CREATE INDEX IF NOT EXISTS idx_bookings_reference ON bookings(booking_reference);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(payment_status);
CREATE INDEX IF NOT EXISTS idx_bookings_details_gin ON bookings USING GIN (booking_details);

-- Create user preferences table
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(255) PRIMARY KEY,
    profile_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create materialized view for quick analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS itinerary_summary AS
SELECT 
    i.itinerary_id,
    i.user_id,
    i.trip_name,
    i.origin,
    i.destination,
    i.start_date,
    i.end_date,
    i.booking_status,
    i.created_at,
    COUNT(b.booking_id) as total_bookings,
    SUM(CASE WHEN b.payment_status = 'completed' THEN 1 ELSE 0 END) as completed_bookings,
    COALESCE(SUM(b.amount_usd), 0) as total_cost_usd
FROM itineraries i
LEFT JOIN bookings b ON i.itinerary_id = b.itinerary_id
GROUP BY i.itinerary_id;

-- Create index on materialized view
CREATE INDEX IF NOT EXISTS idx_itinerary_summary_user ON itinerary_summary(user_id);

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_itinerary_summary()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY itinerary_summary;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
DROP TRIGGER IF EXISTS update_itineraries_updated_at ON itineraries;
CREATE TRIGGER update_itineraries_updated_at 
    BEFORE UPDATE ON itineraries 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_bookings_updated_at ON bookings;
CREATE TRIGGER update_bookings_updated_at 
    BEFORE UPDATE ON bookings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at 
    BEFORE UPDATE ON user_preferences 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your Cloud SQL setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON itineraries TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO your_app_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- Create helpful stored procedures for common operations

-- Procedure to save a complete itinerary
CREATE OR REPLACE FUNCTION save_itinerary(
    p_user_id VARCHAR(255),
    p_trip_name VARCHAR(500),
    p_origin VARCHAR(255),
    p_destination VARCHAR(255),
    p_start_date DATE,
    p_end_date DATE,
    p_itinerary_data JSONB,
    p_booking_status VARCHAR(50) DEFAULT 'booked'
)
RETURNS TABLE (
    itinerary_id INTEGER,
    success BOOLEAN,
    message TEXT
) AS $$
DECLARE
    v_itinerary_id INTEGER;
BEGIN
    INSERT INTO itineraries (
        user_id, trip_name, origin, destination, 
        start_date, end_date, itinerary_data, booking_status
    ) VALUES (
        p_user_id, p_trip_name, p_origin, p_destination,
        p_start_date, p_end_date, p_itinerary_data, p_booking_status
    ) RETURNING itineraries.itinerary_id INTO v_itinerary_id;
    
    RETURN QUERY SELECT v_itinerary_id, TRUE, 'Itinerary saved successfully'::TEXT;
EXCEPTION
    WHEN OTHERS THEN
        RETURN QUERY SELECT NULL::INTEGER, FALSE, SQLERRM::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Procedure to get user itineraries
CREATE OR REPLACE FUNCTION get_user_itineraries(
    p_user_id VARCHAR(255),
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    itinerary_id INTEGER,
    trip_name VARCHAR(500),
    origin VARCHAR(255),
    destination VARCHAR(255),
    start_date DATE,
    end_date DATE,
    booking_status VARCHAR(50),
    created_at TIMESTAMP,
    total_cost_usd NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.itinerary_id,
        s.trip_name,
        s.origin,
        s.destination,
        s.start_date,
        s.end_date,
        s.booking_status,
        s.created_at,
        s.total_cost_usd
    FROM itinerary_summary s
    WHERE s.user_id = p_user_id
    ORDER BY s.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Procedure to get itinerary details
CREATE OR REPLACE FUNCTION get_itinerary_details(
    p_itinerary_id INTEGER
)
RETURNS TABLE (
    itinerary_id INTEGER,
    user_id VARCHAR(255),
    trip_name VARCHAR(500),
    origin VARCHAR(255),
    destination VARCHAR(255),
    start_date DATE,
    end_date DATE,
    itinerary_data JSONB,
    booking_status VARCHAR(50),
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.itinerary_id,
        i.user_id,
        i.trip_name,
        i.origin,
        i.destination,
        i.start_date,
        i.end_date,
        i.itinerary_data,
        i.booking_status,
        i.created_at
    FROM itineraries i
    WHERE i.itinerary_id = p_itinerary_id;
END;
$$ LANGUAGE plpgsql;

-- Procedure to update booking status
CREATE OR REPLACE FUNCTION update_booking_status(
    p_itinerary_id INTEGER,
    p_booking_status VARCHAR(50)
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT
) AS $$
BEGIN
    UPDATE itineraries 
    SET booking_status = p_booking_status,
        updated_at = CURRENT_TIMESTAMP
    WHERE itinerary_id = p_itinerary_id;
    
    IF FOUND THEN
        RETURN QUERY SELECT TRUE, 'Booking status updated successfully'::TEXT;
    ELSE
        RETURN QUERY SELECT FALSE, 'Itinerary not found'::TEXT;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create a view for recent itineraries (useful for dashboards)
CREATE OR REPLACE VIEW recent_itineraries AS
SELECT 
    i.itinerary_id,
    i.user_id,
    i.trip_name,
    i.origin,
    i.destination,
    i.start_date,
    i.end_date,
    i.booking_status,
    i.created_at,
    COUNT(b.booking_id) as booking_count
FROM itineraries i
LEFT JOIN bookings b ON i.itinerary_id = b.itinerary_id
WHERE i.created_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY i.itinerary_id
ORDER BY i.created_at DESC;

-- Sample query to verify setup
-- SELECT * FROM itineraries LIMIT 5;
-- SELECT * FROM itinerary_summary LIMIT 5;
-- SELECT save_itinerary('test_user', 'Test Trip', 'NYC', 'LAX', '2025-12-01', '2025-12-05', '{}'::jsonb);